from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

# Load pre-trained model and tokenizer
model_name = 'gpt2-medium'
tokenizer = GPT2Tokenizer.from_pretrained(model_name)
model = GPT2LMHeadModel.from_pretrained(model_name)

# Encode input text
input_text = "Hello, how are you?"
inputs = tokenizer.encode(input_text, return_tensors="pt")

# Create attention mask
attention_mask = torch.ones_like(inputs)

# Generate response with sampling enabled
outputs = model.generate(
    inputs,
    max_length=50,
    pad_token_id=tokenizer.eos_token_id,
    attention_mask=attention_mask,
    temperature=0.7,
    top_k=50,
    top_p=0.9,
    repetition_penalty=1.2,
    do_sample=True
)

print(tokenizer.decode(outputs[0], skip_special_tokens=True))
