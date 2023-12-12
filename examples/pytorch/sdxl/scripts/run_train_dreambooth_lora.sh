PYTHONPATH=../../.. \
accelerate launch train_dreambooth_lora.py \
  --pretrained_model_name_or_path="AI-ModelScope/stable-diffusion-v1-5"  \
  --instance_data_dir="./xrx" \
  --output_dir="train_dreambooth_lora" \
  --instance_prompt="A photo of xrx girl wearing beautiful dress" \
  --resolution=512 \
  --train_batch_size=4 \
  --gradient_accumulation_steps=4 \
  --checkpointing_steps=100 \
  --learning_rate=1e-4 \
  --report_to="tensorboard" \
  --lr_scheduler="constant" \
  --lr_warmup_steps=0 \
  --max_train_steps=500 \
  --validation_prompt="A photo of xrx girl wearing beautiful dress" \
  --validation_epochs=50 \
  --seed="0"