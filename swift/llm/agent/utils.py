# Copyright (c) Alibaba, Inc. and its affiliates.
import os
from typing import List, Tuple

from swift.utils import get_logger
from swift.utils.utils import split_str_parts_by

logger = get_logger()


def calculate_loss_scale(response: str, use_loss_scale=False) -> Tuple[List[str], List[float]]:
    """Calculate the loss scale by splitting the agent response.

    This algorithm comes from paper: https://arxiv.org/pdf/2309.00986.pdf

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
        use_loss_scale: Use weighted loss. With this, some part of the loss will be enhanced to improve performance.

    Returns:
        A tuple of agent response parts and their weights.
    """
    if os.environ.get('outline', None) == '1':
        if 'outline:' in response:
            parts = split_str_parts_by(response, ['outline:', 'answer:',
                                                'Thought finished', 'thought finished', 'Thought Finished'])
            weights = []
            contents = []
            for c in parts:
                if c['key'] == 'outline:':
                    if c['content'].strip():
                        weights += [1.0]
                        contents.append(c['content'])
                elif c['key'].lower() == 'thought finished':
                    # weights += [1.0]
                    weights += [0.0]
                    if c['content'].startswith('.'):
                        c['content'] = c['content'][1:]
                    # contents.append(c['key'] + '.')
                    contents.append(c['content'])
                else:
                    weights += [0.0]
                    contents.append(c['content'])
            return contents, weights
        else:
            return [response], [0.0]
    if 'Action:' in response and use_loss_scale:
        agent_keyword = ['Action:', 'Action Input:', 'Thought:',
                         'Final Answer:', 'Observation:', 'outline:', 'answer:',
                         'Thought finished', 'thought finished', 'Thought Finished']
        agent_parts = split_str_parts_by(response, agent_keyword)
        weights = []
        agent_content = []
        for c in agent_parts:
            if c['key'] in ('Action:', 'Action Input:'):
                weights += [1.0]
                weights += [1.0]
                agent_content.append(c['key'])
                agent_content.append(c['content'])
            elif c['key'] in ('Thought:', 'Final Answer:', ''):
                weights += [1.0]
                weights += [1.0]
                agent_content.append(c['key'])
                agent_content.append(c['content'])
            elif c['key'] in ('Observation:', ):
                weights += [1.0]
                weights += [0.0]
                agent_content.append(c['key'])
                agent_content.append(c['content'])
            elif c['key'] == 'outline:':
                if c['content'].strip():
                    weights += [0.0]
                    agent_content.append(c['content'])
            elif c['key'] == 'answer:':
                if c['content'].strip():
                    weights += [2.0]
                    agent_content.append(c['content'])
            elif c['key'].lower() == 'thought finished':
                # weights += [0.0]
                weights += [1.0]
                if c['content'].startswith('.'):
                    c['content'] = c['content'][1:]
                # agent_content.append(c['key'] + '.')
                agent_content.append(c['content'])
        return agent_content, weights
    elif ('Action:' in response or 'Next:' in response) and use_loss_scale:  # alpha-umi
        agent_keyword = ['Next:', 'Action:', 'Action Input:']
        agent_parts = split_str_parts_by(response, agent_keyword)
        weights = []
        agent_content = []
        for c in agent_parts:
            if c['key'] in ('Action:', 'Action Input:', 'Next:'):
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
