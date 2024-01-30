# Copyright (c) Alibaba, Inc. and its affiliates.
from types import MethodType
from typing import List, Tuple

from peft import PeftModel as HFPeftModel

from swift import PeftModel, SwiftModel
from swift.utils import get_logger

logger = get_logger()


def split_agent_parts_by(text: str, delimiters: List[str]):
    """Split the text field into parts.

    Args:
        text: A text to be split.
        delimiters: The delimiters.

    Returns:
        The split text in list of dicts.
    """
    all_start_chars = [d[0] for d in delimiters]
    all_length = [len(d) for d in delimiters]

    text_list = []
    last_words = ''

    while len(text) > 0:
        for char_idx, char in enumerate(text):
            match_index = [
                idx for idx, start_char in enumerate(all_start_chars)
                if start_char == char
            ]
            is_delimiter = False
            for index in match_index:
                if text[char_idx:char_idx
                        + all_length[index]] == delimiters[index]:
                    if last_words:
                        if text_list:
                            text_list[-1]['content'] = last_words
                        else:
                            text_list.append({
                                'key': '',
                                'content': last_words
                            })
                    last_words = ''
                    text_list.append({'key': delimiters[index]})
                    text = text[char_idx + all_length[index]:]
                    is_delimiter = True
                    break
            if not is_delimiter:
                last_words += char
            else:
                break
        if last_words == text:
            text = ''

    text_list[-1]['content'] = last_words
    return text_list


def calculate_loss_scale(response: str) -> Tuple[List[str], List[float]]:
    """Calculate the loss scale by splitting the agent response.

    Agent response format:

    ```text
        Thought: you should always think about what to do
        Action: the action to take, should be one of the above tools[fire_recognition,
            fire_alert, call_police, call_fireman]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question
    ```

    Args:
        response: The response text

    Returns:
        A tuple of agent response parts and their weights.
    """
    if 'Action:' in response and 'Thought:' in response:
        agent_keyword = [
            'Action:', 'Action Input:', 'Thought:', 'Final Answer:',
            'Observation:'
        ]
        agent_parts = split_agent_parts_by(response, agent_keyword)
        assert all([c['key'] for c in agent_parts])
        weights = []
        agent_content = []
        for c in agent_parts:
            if c['key'] in ('Action:', 'Action Input:'):
                weights += [2.0]
                weights += [2.0]
            elif c['key'] in ('Thought:', 'Final Answer:', ''):
                weights += [1.0]
                weights += [1.0]
            elif c['key'] in ('Observation:', ):
                weights += [2.0]
                weights += [0.0]
            agent_content.append(c['key'])
            agent_content.append(c['content'])
        return agent_content, weights
    else:
        return [response], [1.0]


def prepare_loss_scale(model):
    """Prepare the loss scale by model.
    """
    if isinstance(model, (SwiftModel, PeftModel, HFPeftModel)):
        model = model.base_model

    if model.__class__.__name__ == 'ChatGLMForConditionalGeneration':
        from .models import ChatGLM3Forward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(ChatGLM3Forward, model)
        else:
            model.forward = MethodType(ChatGLM3Forward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'InternLM2ForCausalLM':
        from .models import InternLMForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(InternLMForward, model)
        else:
            model.forward = MethodType(InternLMForward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'QWenLMHeadModel':
        from .models import QwenForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(QwenForward, model)
        else:
            model.forward = MethodType(QwenForward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'LlamaForCausalLM':
        from .models import LLaMAForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(LLaMAForward, model)
        else:
            model.forward = MethodType(LLaMAForward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'MistralForCausalLM':
        from .models import MistralForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(MistralForward, model)
        else:
            model.forward = MethodType(MistralForward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'XverseForCausalLM':
        from .models import XverseForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(XverseForward, model)
        else:
            model.forward = MethodType(XverseForward, model)
        model.support_loss_scale = True
    elif model.__class__.__name__ == 'XverseForCausalLM':
        from .models import XverseForward
        if hasattr(model, '_old_forward'):
            model._old_forward = MethodType(XverseForward, model)
        else:
            model.forward = MethodType(XverseForward, model)
        model.support_loss_scale = True
    else:
        model.support_loss_scale = False
        logger.warn(
            f'Model {model.__class__.__name__} not supported for weight scaling'
        )
