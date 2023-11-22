# Copyright (c) Alibaba, Inc. and its affiliates.
from swift.llm import (AnimateDiffArguments, InferArguments, RomeArguments, AnimateDiffInferArguments,
                       SftArguments, animatediff_sft, get_main, llm_infer, animatediff_infer,
                       llm_sft, llm_web_ui, rome_infer)

sft_main = get_main(SftArguments, llm_sft)
infer_main = get_main(InferArguments, llm_infer)
rome_main = get_main(RomeArguments, rome_infer)
web_ui_main = get_main(InferArguments, llm_web_ui)
animatediff_main = get_main(AnimateDiffArguments, animatediff_sft)
animatediff_infer_main = get_main(AnimateDiffInferArguments, animatediff_infer)
