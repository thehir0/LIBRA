import os
import argparse
import json

from evaluation import dataset_loader, model_loader, answer_generator
from configparser import ConfigParser
from huggingface_hub import login


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="Enter config path", required=True)
    parser.add_argument("-t", "--token", help="Enter Hugging Face token")
    args = parser.parse_args()

    if args.token:
        login(token=args.token)

    config = ConfigParser()
    config.read(args.config)

    engine = json.loads(config.get('parameters', 'engine'))

    tensor_parallel_size = int(json.loads(config.get('parameters', 'tensor_parallel_size')))
    gpu_memory_utilization = float(json.loads(config.get('parameters', 'gpu_memory_utilization')))
    datasets_names = json.loads(config.get('parameters', 'datasets'))
    context_lengths = json.loads(config.get('parameters', 'context_lengths'))
    max_context_length = int(config.get('parameters', 'max_context_length'))
    model_path = config.get('parameters', 'model_path')
    tokenizer_path = config.get('parameters', 'tokenizer_path')
    model_torch_dtype = config.get('parameters', 'model_torch_dtype')
    device = config.get('parameters', 'device')
    save_path = config.get('parameters', 'save_path')
    
    if engine == 'hf':
        model_loader = model_loader.ModelLoader(model_path=model_path,
                                                model_torch_dtype=model_torch_dtype,
                                                tokenizer_path=tokenizer_path,
                                                device=device)
    elif engine == 'vllm':
        model_loader = model_loader.vLLM_ModelLoader(model_path=model_path,
                                        model_torch_dtype=model_torch_dtype,
                                        tokenizer_path=tokenizer_path,
                                        gpu_memory_utilization=gpu_memory_utilization,
                                        tensor_parallel_size=tensor_parallel_size,
                                        device=device)
    else:
        raise Exception('Engine should be \"hf\" or \"vllm\"')

    model, tokenizer = model_loader.model_load()
    
    datasets_params = json.load(open("configs/datasets_config.json", "r", encoding="utf-8"))

    if "all" in datasets_names:
        datasets_names = list(datasets_params.keys())

    print("Your model is evaluating on next tasks: ", datasets_names)
    results = {}
    for dataset_name in datasets_names:
        print(dataset_name)
        data_loader = dataset_loader.DatasetLoader(dataset_name=dataset_name)
        dataset = data_loader.dataset_load()
        max_new_tokens = int(datasets_params[dataset_name]["max_new_tokens"])
        instruction = datasets_params[dataset_name]["instruction"]

        if engine == 'hf':
            pred_generator = answer_generator.AnswerGenerator(model=model,
                                                            tokenizer=tokenizer,
                                                            device=device,
                                                            dataset=dataset,
                                                            instruction=instruction,
                                                            context_lengths=context_lengths,
                                                            max_context_length=max_context_length,
                                                            max_new_tokens=max_new_tokens)
        elif engine == 'vllm':
            pred_generator = answer_generator.vLLM_AnswerGenerator(model=model,
                                                tokenizer=tokenizer,
                                                device=device,
                                                dataset=dataset,
                                                instruction=instruction,
                                                context_lengths=context_lengths,
                                                max_context_length=max_context_length,
                                                max_new_tokens=max_new_tokens)
        else:
            raise Exception('Engine should be \"hf\" or \"vllm\"')

        pred_generator = answer_generator.AnswerGenerator(
            model=model,
            tokenizer=tokenizer,
            device=device,
            dataset=dataset,
            instruction=instruction,
            context_lengths=context_lengths,
            max_context_length=max_context_length,
            max_new_tokens=max_new_tokens,
            chat_model=chat_model,
            sys_prompt=sys_prompt,
        )
        generated_answers = pred_generator.generate_answers()
        results[dataset_name] = generated_answers

    if not os.path.exists(save_path.split("/")[0]):
        os.makedirs(save_path.split("/")[0])
    with open(save_path, "w") as outfile:
        json.dump(results, outfile)
    print(f"predictions were saved here: {save_path}")
