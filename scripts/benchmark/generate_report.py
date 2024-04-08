# Copyright (c) Alibaba, Inc. and its affiliates.
import dataclasses
import json
import os
from dataclasses import dataclass
from typing import Dict, Any, List

from swift.utils.utils import split_str_parts_by


@dataclass
class ModelOutput:
    name: str = None

    cmd: str = None

    requirements: Dict[str, str] = dataclasses.field(default_factory=dict)

    args: Dict[str, Any] = dataclasses.field(default_factory=dict)

    memory: str = None

    train_time: float = None

    train_samples: int = None

    train_samples_per_second: float = None

    last_model_checkpoint: str = None

    best_model_checkpoint: str = None

    best_metric: Any = None

    global_step: int = None

    num_total_parameters: float = None

    num_trainable_parameters: float = None

    num_buffers: float = None

    trainable_parameters_percentage: float = None

    train_dataset_info: str = None

    val_dataset_info: str = None

    train_create_time: float = None

    eval_tokens: int = None

    eval_time: float = None

    reports: Dict[str, Any] = None

    train_loss: float = None

    @property
    def tuner_hyper_params(self):
        hyper_params = ''
        args = self.args
        if 'sft_type' not in args:
            return ''
        if args['sft_type'] in ('lora', 'adalora', 'longlora'):
            hyper_params += f'rank={args["lora_rank"]}/' \
                            f'target={args["lora_target_modules"]}/' \
                            f'alpha={args["lora_alpha"]}/' \
                            f'lr_ratio={args.get("lora_lr_ratio", None)}/' \
                            f'use_rslora={args.get("use_rslora", False)}/' \
                            f'use_dora={args.get("use_dora", False)}'
        if args['sft_type'] == 'full':
            if 'use_galore' in args and args['use_galore'] == 'true':
                hyper_params += f'galore_rank={args["galore_rank"]}/' \
                                f'galore_per_parameter={args["galore_optim_per_parameter"]}/' \
                                f'galore_with_embedding={args["galore_with_embedding"]}/'
        if args['sft_type'] == 'llamapro':
            hyper_params += f'num_blocks={args["llamapro_num_new_blocks"]}/'
        if 'neftune_noise_alpha' in args and args['neftune_noise_alpha']:
            hyper_params += f'neftune_alpha={args["neftune_noise_alpha"]}/'

        if hyper_params.endswith('/'):
            hyper_params = hyper_params[:-1]
        return hyper_params

    @property
    def hyper_paramters(self):
        if 'learning_rate' not in self.args:
            return ''
        return f'lr={self.args["learning_rate"]}/' \
                       f'epoch={self.args["num_train_epochs"]}'

    @property
    def train_speed(self):
        return f'{self.train_samples_per_second}({self.train_samples} samples/{self.train_time} seconds)'

    @property
    def infer_speed(self):
        if self.eval_tokens:
            return f'{self.eval_tokens / self.eval_time}({self.eval_tokens} tokens/{self.eval_time} seconds)'
        return ''


def generate_sft_report(outputs: List[ModelOutput]):
    tab = '| exp_name | model_type | dataset | mix_ratio | tuner | tuner_params | flash_attn | gradient_checkpointing | hypers | memory | train speed(samples/s) | infer speed(tokens/s) | train_loss | eval_loss | gsm8k weighted acc | arc weighted acc | ceval weighted acc |\n' \
          '| -------- | ---------- | ------- | ----------| ----- | ------------ | -----------| ---------------------- | ------ | ------ | ---------------------- | --------------------- | ---------- | --------- | ------------------ | ---------------- | ------------------ |\n'
    for output in outputs:
        use_flash_attn = output.args.get('use_flash_attn', '')
        use_gc = output.args.get('gradient_checkpointing', '')
        memory = output.memory

        train_speed = output.train_speed

        infer_speed = output.infer_speed
        gsm8k_acc = ''
        arc_acc = ''
        ceval_acc = ''
        for report in (output.reports or []):
            if report['name'] == 'gsm8k':
                gsm8k_acc = report['score']
            if report['name'] == 'arc':
                arc_acc = report['score']
            if report['name'] == 'ceval':
                ceval_acc = report['score']

        line = f'|{output.name}|' \
               f'{output.args["model_type"]}|' \
               f'{output.args.get("dataset")}|' \
               f'{output.args.get("train_dataset_mix_ratio", 0.)}|' \
               f'{output.args.get("sft_type")}|' \
               f'{output.tuner_hyper_params}|' \
               f'{use_flash_attn}|' \
               f'{use_gc}|' \
               f'{output.hyper_paramters}|' \
               f'{memory}|' \
               f'{train_speed}|' \
               f'{infer_speed}|' \
               f'{output.best_metric}|' \
               f'{output.train_loss}|' \
               f'{gsm8k_acc}|' \
               f'{arc_acc}|' \
               f'{ceval_acc}|\n'
        tab += line
    return tab


def generate_export_report(outputs: List[ModelOutput]):
    tab = '| exp_name | model_type | dataset | quantization method | quantization bits | infer speed(tokens/s) | gsm8k weighted acc | arc weighted acc | ceval weighted acc |\n' \
          '| -------- | ---------- | ------- | ------------------- | ----------------- | --------------------- | ------------------ | ---------------- | ------------------ |\n'
    for output in outputs:
        infer_speed = output.infer_speed
        gsm8k_acc = ''
        arc_acc = ''
        ceval_acc = ''
        for report in (output.reports or []):
            if report['name'] == 'gsm8k':
                gsm8k_acc = report['score']
            if report['name'] == 'arc':
                arc_acc = report['score']
            if report['name'] == 'ceval':
                ceval_acc = report['score']

        line = f'|{output.name}|' \
               f'{output.args["model_type"]}|' \
               f'{output.args["dataset"]}/{output.train_dataset_info}|' \
               f'{output.args["quant_method"]}|' \
               f'{output.args["quant_bits"]}|' \
               f'{infer_speed}|' \
               f'{gsm8k_acc}|' \
               f'{arc_acc}|' \
               f'{ceval_acc}|\n'
        tab += line
    return tab


def parse_output(file):
    with open(file, 'r') as f:
        content = json.load(f)

    name = content['name']
    cmd = content['cmd']
    requirements = content['requirements']
    args = content['args']
    create_time = float(content.get('create_time') or 0)
    content = content['record']
    if cmd == 'export':
        best_model_checkpoint = content['best_model_checkpoint']
        eval_tokens = 0
        eval_time = 0.0
        eval_result = None
        if 'eval_result' in content:
            eval_result = content['eval_result']
            eval_tokens = eval_result['generation_info']['tokens']
            eval_time = eval_result['generation_info']['time']
            eval_result = eval_result['report']
        return ModelOutput(
            name=name,
            cmd=cmd,
            requirements=requirements,
            args=args,
            best_model_checkpoint=best_model_checkpoint,
            eval_time=eval_time,
            eval_tokens=eval_tokens,
            reports=eval_result,
        )
    else:
        memory = None
        train_time = None
        train_samples = None
        train_samples_per_second = None
        last_model_checkpoint = None
        best_model_checkpoint = None
        best_metric = None
        global_step = None
        train_dataset_info = None
        val_dataset_info = None
        num_trainable_parameters = None
        num_buffers = None
        trainable_parameters_percentage = None
        num_total_parameters = None
        train_loss = None
        if 'memory' in content:
            memory = content['memory']
            memory = '/'.join(memory.values())
        if 'train_time' in content:
            train_time = content['train_time']['train_runtime']
            train_samples = content['train_time']['n_train_samples']
            train_samples_per_second = content['train_time'][
                'train_samples_per_second']
        if 'last_model_checkpoint' in content:
            last_model_checkpoint = content['last_model_checkpoint']
        if 'best_model_checkpoint' in content:
            best_model_checkpoint = content['best_model_checkpoint']
        if 'best_metric' in content:
            best_metric = content['best_metric']
        if 'log_history' in content:
            train_loss = content['log_history'][-1]['train_loss']
        if 'global_step' in content:
            global_step = content['global_step']
        if 'dataset_info' in content:
            train_dataset_info = content['dataset_info']['train_dataset']
            val_dataset_info = content['dataset_info']['val_dataset']
        if 'model_info' in content:
            # model_info like: SwiftModel: 6758.4041M Params (19.9885M Trainable [0.2958%]), 16.7793M Buffers.
            str_dict = split_str_parts_by(content['model_info'], [
                'SwiftModel:', 'CausalLM:', 'Seq2SeqLM:', 'LMHeadModel:', 'M Params (',
                'M Trainable [', ']), ', 'M Buffers.'
            ])
            str_dict = {c['key']: c['content'] for c in str_dict}
            if 'SwiftModel:' in str_dict:
                num_total_parameters = float(str_dict['SwiftModel:'])
            elif 'CausalLM:' in str_dict:
                num_total_parameters = float(str_dict['CausalLM:'])
            elif 'Seq2SeqLM:' in str_dict:
                num_total_parameters = float(str_dict['Seq2SeqLM:'])
            elif 'LMHeadModel:' in str_dict:
                num_total_parameters = float(str_dict['LMHeadModel:'])
            num_trainable_parameters = float(str_dict['M Params ('])
            num_buffers = float(str_dict[']), '])
            trainable_parameters_percentage = str_dict['M Trainable [']

        eval_tokens = 0
        eval_time = 0.0
        eval_result = None
        if 'eval_result' in content:
            eval_result = content['eval_result']
            eval_tokens = eval_result['generation_info']['tokens']
            eval_time = eval_result['generation_info']['time']
            eval_result = eval_result['report']

        return ModelOutput(
            name=name,
            cmd=cmd,
            requirements=requirements,
            args=args,
            memory=memory,
            train_time=train_time,
            train_samples=train_samples,
            train_samples_per_second=train_samples_per_second,
            last_model_checkpoint=last_model_checkpoint,
            best_model_checkpoint=best_model_checkpoint,
            best_metric=best_metric,
            global_step=global_step,
            train_dataset_info=train_dataset_info,
            val_dataset_info=val_dataset_info,
            train_create_time=create_time,
            num_total_parameters=num_total_parameters,
            num_trainable_parameters=num_trainable_parameters,
            num_buffers=num_buffers,
            trainable_parameters_percentage=trainable_parameters_percentage,
            eval_time=eval_time,
            eval_tokens=eval_tokens,
            reports=eval_result,
            train_loss=train_loss,
        )


def generate_reports():
    outputs = []
    for dirs, _, files in os.walk('./experiment'):
        for file in files:
            abs_file = os.path.join(dirs, file)
            if not abs_file.endswith('.json') or 'ipynb' in abs_file:
                continue

            outputs.append(parse_output(abs_file))

    print(generate_sft_report([output for output in outputs if output.cmd in ('sft', 'eval')]))
    # print(generate_dpo_report([output for output in outputs if output.cmd == 'dpo']))
    print(generate_export_report([output for output in outputs if output.cmd == 'export']))


if __name__ == '__main__':
    generate_reports()
