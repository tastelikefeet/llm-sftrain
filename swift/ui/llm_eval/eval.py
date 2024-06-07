import os.path
from typing import Type

import gradio as gr

from swift.ui.base import BaseUI

class Eval(BaseUI):

    group = 'llm_eval'

    locale_dict = {
        'name': {
            'label': {
                'zh': '评测名称',
                'en': 'Evaluation name'
            },
            'info': {
                'zh': '支持英文字母、下划线、横线和数字',
                'en': 'Support characters, underscores, hyphens and numbers'
            }
        },
        'eval_dataset': {
            'label': {
                'zh': '评测数据集',
                'en': 'Evaluation dataset'
            },
            'info': {
                'zh': '选择评测数据集，支持多选',
                'en': 'Select eval dataset, multiple datasets supported'
            }
        },
        'eval_few_shot': {
            'label': {
                'zh': 'prompt的few-shot',
                'en': 'The few-shot for the prompt'
            },
            'info': {
                'zh': 'Few-shot数量在评测集中有默认设置，可以不填',
                'en': 'Few-shot numbers have default values in different datasets'
            }
        },
        'eval_limit': {
            'label': {
                'zh': '评测数据个数',
                'en': 'Eval numbers for each dataset'
            },
            'info': {
                'zh': '每个评测集的取样数',
                'en': 'Number of rows sampled from each dataset'
            }
        },
        'eval_use_cache': {
            'label': {
                'zh': '使用缓存',
                'en': 'Use eval cache'
            },
            'info': {
                'zh': '如果name指定的评测已经存在，则可以使用已有缓存',
                'en': 'If the evaluation results of the name exists, you may use cache.'
            }
        },
        'custom_eval_config': {
            'label': {
                'zh': '自定义数据集评测配置',
                'en': 'Custom eval config'
            },
            'info': {
                'zh': '可以使用该配置评测自己的数据集，详见github文档的评测部分',
                'en': 'Use this config to eval your own datasets, check the docs in github for details'
            }
        },
        'eval_url': {
            'label': {
                'zh': '评测链接',
                'en': 'The eval url'
            },
            'info': {
                'zh': 'OpenAI样式的评测链接，用于评测接口(模型选择http接口)',
                'en': 'The OpenAI style link for evaluation(Choose http interface in model_type)'
            }
        },
        'eval_token': {
            'label': {
                'zh': 'Url token',
                'en': 'The url token'
            },
        },
        'eval_is_chat_model': {
            'label': {
                'zh': '接口是chat模型',
                'en': 'Chat model'
            },
            'info': {
                'zh': '评测接口是否是Chat模型',
                'en': 'The eval url is a chat model or not'
            }
        },
    }

    @classmethod
    def do_build_ui(cls, base_tab: Type['BaseUI']):
        with gr.Row():
            name = gr.Textbox(elem_id='name', scale=20)
            eval_dataset = gr.Dropdown(elem_id='eval_dataset', is_list=True, multiselect=True, scale=20)
            eval_few_shot = gr.Textbox(elem_id='eval_few_shot', scale=20)
            eval_limit = gr.Textbox(elem_id='eval_limit', scale=20)
            eval_use_cache = gr.Checkbox(elem_id='eval_use_cache', scale=20)
        with gr.Row():
            custom_eval_config = gr.Textbox(elem_id='custom_eval_config', scale=20)
        with gr.Row():
            eval_url = gr.Textbox(elem_id='eval_url', scale=20)
            eval_token = gr.Textbox(elem_id='eval_token', scale=20)
            eval_is_chat_model = gr.Checkbox(elem_id='eval_is_chat_model', scale=20)
