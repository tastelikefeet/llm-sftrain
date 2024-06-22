# Copyright (c) Alibaba, Inc. and its affiliates.
import asyncio
import datetime as dt
import multiprocessing
import os
import subprocess
import time
from dataclasses import fields
from typing import Any, Dict, List, Optional, Tuple

import json
from llmuses.backend.opencompass import OpenCompassBackendManager
from llmuses.run import run_task
from modelscope import GenerationConfig
from tqdm import tqdm

from swift.utils import append_to_jsonl, get_logger, get_main, seed_everything, safe_ddp_context
from . import DeployArguments
from .infer import merge_lora, prepare_model_template
from .utils import EvalArguments, XRequestConfig, inference, inference_client_async

logger = get_logger()


class EvalModel(CustomModel):

    def __init__(self, args: EvalArguments, model_name: str, **kwargs) -> None:
        if args.eval_url is None:
            if args.merge_lora:
                merge_lora(args, device_map=args.merge_device_map)
            if args.infer_backend == 'vllm':
                from .utils import prepare_vllm_engine_template
                self.llm_engine, self.template = prepare_vllm_engine_template(args)
            else:
                self.model, self.template = prepare_model_template(args)

        self.args = args
        super().__init__(config={'model_id': model_name}, **kwargs)
        self.model_name = model_name

    @staticmethod
    async def _call_openai(model_type: str, query: str, eval_url: str, *, is_chat_model: bool,
                           request_config: XRequestConfig, idx: int) -> Tuple[str, Optional[int]]:
        # idx: maintain the order
        resp = await inference_client_async(
            model_type, query, is_chat_request=is_chat_model, request_config=request_config, url=eval_url)
        if is_chat_model:
            response = resp.choices[0].message.content
        else:
            response = resp.choices[0].text
        return response, idx

    async def call_openai_batched(self, prompts: List[str], request_config: XRequestConfig) -> List[str]:
        assert self.args.eval_is_chat_model is not None
        use_tqdm = True if len(prompts) >= 20 else False
        prog_bar = tqdm(total=len(prompts), dynamic_ncols=True, disable=not use_tqdm)
        tasks = []
        for i, prompt in enumerate(prompts):
            tasks.append(
                self._call_openai(
                    self.args.model_type,
                    prompt,
                    self.args.eval_url,
                    is_chat_model=self.args.eval_is_chat_model,
                    request_config=request_config,
                    idx=i))
        response_list: List[Optional[str]] = [None] * len(prompts)
        for coro in asyncio.as_completed(tasks):
            response, i = await coro
            response_list[i] = response
            prog_bar.update()
        prog_bar.close()
        return response_list

    def predict(self, prompts: List[str], **kwargs) -> List[Dict[str, Any]]:
        infer_cfg = kwargs['infer_cfg'].copy()
        infer_cfg.pop('limit', None)
        infer_cfg.pop('max_length', None)
        assert infer_cfg.get('max_new_tokens') is not None, f'infer_cfg: {infer_cfg}'
        do_sample = infer_cfg.pop('do_sample', None)

        if self.args.eval_url is not None:
            if do_sample is False:
                infer_cfg['temperature'] = 0
            max_new_tokens = infer_cfg.pop('max_new_tokens', None)
            if max_new_tokens is not None:
                infer_cfg['max_tokens'] = max_new_tokens

            request_config = XRequestConfig(**infer_cfg)
            response_list = asyncio.run(self.call_openai_batched(prompts, request_config))

        elif self.args.infer_backend == 'vllm':
            from .utils import inference_vllm, VllmGenerationConfig
            if do_sample is False:
                infer_cfg['temperature'] = 0
            generation_config = VllmGenerationConfig(**infer_cfg)

            request_list = [{'query': prompt} for prompt in prompts]
            use_tqdm = True if len(request_list) >= 20 else False
            resp_list = inference_vllm(
                self.llm_engine, self.template, request_list, generation_config=generation_config, use_tqdm=use_tqdm)
            response_list = [resp['response'] for resp in resp_list]
        else:
            if do_sample is False:
                # fix warning
                infer_cfg['temperature'] = 1.
                infer_cfg['top_p'] = 1.
                infer_cfg['top_k'] = 50
            if do_sample is not None:
                infer_cfg['do_sample'] = do_sample
            response_list = []
            generation_config = GenerationConfig(**infer_cfg)
            use_tqdm = True if len(prompts) >= 5 else False
            prog_bar = tqdm(total=len(prompts), dynamic_ncols=True, disable=not use_tqdm)
            for prompt in prompts:
                response, _ = inference(self.model, self.template, prompt, generation_config=generation_config)
                response_list.append(response)
                prog_bar.update()
            prog_bar.close()
        res_d = []
        for response in response_list:
            res_d.append({
                'choices': [{
                    'index': 0,
                    'message': {
                        'content': response,
                        'role': 'assistant'
                    }
                }],
                'created': int(time.time()),
                'model': self.model_name,
                'object': 'chat.completion',
            })
        return res_d


def run_custom_model(args: EvalArguments):
    from swift.utils.torch_utils import _find_free_port
    from swift.llm.deploy import llm_deploy
    deploy_args = DeployArguments()
    for f in fields(args):
        if hasattr(deploy_args, f.name):
            setattr(deploy_args, f.name, getattr(args, f.name))
    deploy_args.port = _find_free_port()
    llm_deploy(deploy_args)


class EvalDatasetContext:

    def __init__(self):
        self.cache_dir = self.prepare_evalscope_dataset()

    def __enter__(self):
        os.symlink(self.cache_dir, os.path.join(os.getcwd(), 'data'))

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.islink(os.path.join(os.getcwd(), 'data')):
            os.remove(os.path.join(os.getcwd(), 'data'))

    @staticmethod
    def prepare_evalscope_dataset():
        from swift.llm.utils.media import MediaCache
        data_url = 'https://github.com/open-compass/opencompass/releases/download/0.2.2.rc1/OpenCompassData-core-20240207.zip'
        return MediaCache.download(data_url, 'evalscope')



def llm_eval(args: EvalArguments) -> List[Dict[str, Any]]:
    from llmuses.run import run_task
    from llmuses.config import TaskConfig
    from llmuses.summarizer import Summarizer
    from swift.utils.torch_utils import _find_free_port
    logger.info(f'args: {args}')
    seed_everything(args.seed)
    model_name = args.model_type
    if args.name:
        model_name += f'-{args.name}'
    custom_names = []
    if args.custom_eval_config is not None:
        assert os.path.isfile(args.custom_eval_config)
        with open(args.custom_eval_config, 'r') as f:
            custom_eval = json.load(f)
            for _ds in custom_eval:
                custom_names.append(_ds['name'])
                TaskConfig.registry(_ds['name'], _ds['pattern'], _ds['dataset'], subset_list=_ds.get('subset_list'))

    port = _find_free_port()
    args.port = port
    process = multiprocessing.Process(target=run_custom_model, args=(args,))
    process.start()

    model_type = 'default-lora' if args.sft_type == 'lora' and not args.merge_lora else args.model_type

    task_cfg = dict(
        eval_backend='OpenCompass',
        eval_config={'datasets': args.eval_dataset,
                     'models': [
                         {'path': model_type, 'openai_api_base': f'http://127.0.0.1:{port}/v1/chat/completions'}, ]
                     },
    )

    with EvalDatasetContext():
        run_task(task_cfg=task_cfg)

    # task_configs = TaskConfig.load(custom_model=eval_model, tasks=args.eval_dataset + custom_names)
    # for task_config in task_configs:
    #     task_config.use_cache = args.eval_use_cache
    #     if args.eval_limit is not None:
    #         task_config.limit = args.eval_limit
    #     if args.eval_few_shot is not None:
    #         for dataset in task_config.datasets:
    #             if not task_config.dataset_args.get(dataset):
    #                 task_config.dataset_args[dataset] = {}
    #             task_config.dataset_args[dataset]['few_shot_num'] = args.eval_few_shot

    # run_task(task_cfg=task_configs)
    # final_report: List[dict] = Summarizer.get_report_from_cfg(task_cfg=task_configs)
    # logger.info(f'Final report:{final_report}\n')
    #
    # if args.save_result:
    #     result_dir = args.ckpt_dir
    #     if result_dir is None:
    #         result_dir = eval_model.llm_engine.model_dir if args.infer_backend == 'vllm' else eval_model.model.model_dir
    #     assert result_dir is not None
    #     jsonl_path = os.path.join(result_dir, 'eval_result.jsonl')
    #     result = {report['name']: report['score'] for report in final_report}
    #     logger.info(f'result: {result}')
    #     result_info = {
    #         'result': result,
    #         'time': dt.datetime.now().strftime('%Y%m%d-%H%M%S'),
    #     }
    #     append_to_jsonl(jsonl_path, result_info)
    #     logger.info(f'save_result_path: {jsonl_path}')
    # return final_report


eval_main = get_main(EvalArguments, llm_eval)
