import json
import time
from dataclasses import dataclass
from typing import List, Optional
import requests

from tqdm import tqdm
from subtitle import SubtitleBlock, parse_srt,save_srt,split_long_subtitle_blocks,merge_subtitles,CMD_FFMPEG_MERGE_TEMPLATE, CMD_FFMPEG_SPLIT_TEMPLATE

@dataclass
class ModelConfigOpenAI:
    api_url: str = "https://api.siliconflow.cn/v1"
    model_id: str = "deepseek-ai/DeepSeek-V3"  # 强制指定模型[^1]
    api_key: str = "YOUR_API_KEY"
    headers: dict = None
    
    def __post_init__(self):
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

@dataclass
class ModelConfigOllama:
    """Ollama专用配置类"""
    api_url: str = "http://localhost:11434"  # 默认本地地址[^1]
    model_id: str = "llama3.2"  # 必须指定模型名称[^1]
    num_ctx: int = 4096         # 上下文窗口大小[^3]
    temperature: float = 0.3    # 输出随机性控制[^1]
    top_p: float = 0.9          # Top-p采样参数[^1]
    stream: bool = False        # 流式响应开关[^1]
    keep_alive: str = "5m"      # 模型内存驻留时间[^1]
    headers: dict = None        # 自定义请求头
    
    def __post_init__(self):
        self.headers = self.headers or {}
        # 自动添加必要头信息[^3]
        self.headers.setdefault("Content-Type", "application/json")
        
def parse_srt(file_path: str) -> List[SubtitleBlock]:
    """SRT文件解析器"""
    blocks = []
    with open(file_path, 'r', encoding='utf-8') as f:
        current_block = None
        for line in f:
            line = line.strip()
            if line.isdigit():
                current_block = SubtitleBlock(index=int(line), timeline="", text="")
            elif '-->' in line:
                current_block.timeline = line
            elif line:
                current_block.text += line + " "
            elif current_block and current_block.text:
                current_block.text = current_block.text.strip()
                blocks.append(current_block)
                current_block = None
        if current_block and current_block.text:  # 处理最后未完结块[^3]
            blocks.append(current_block)
    return blocks

def get_context_window(blocks: List[SubtitleBlock], current_index: int, window_size=50) -> str:
    """获取动态上下文窗口"""
    if not window_size:
        return "<NO_CONTEXT>"
    start = max(0, current_index - window_size)
    end = min(len(blocks), current_index + window_size + 1)
    return " | ".join([block.text for block in blocks[start:end]])

def translate_block_openai(
    config: ModelConfigOpenAI,
    block: SubtitleBlock,
    context: str,
    domain: Optional[str]
) -> str:
    """动态翻译单个字幕块"""
    system_prompt = (
        f"你是一个资深的{domain or '通用'}领域的字幕翻译专家，严格遵守以下规则：\n"
        "1. 仅输出简体中文译文\n"
        "2. 根据上下文参考给出最符合语境的翻译\n"
        "3. 确保译文语序和表述符合中文正确的语言习惯\n"
        "4. 自动校正原文中可能存在的的拼写错误\n"
        "5. 猜想并保持原始文本的风格和语气\n"
        "6. 专业技术词汇请参考当前领域知识进行翻译\n"
        f"当前领域：{domain or '通用领域'}"
        "请严格按要求直接输出中文译文（不要添加任何解释或符号）"
    )
    
    user_prompt = (
        f"上下文参考：\n{context}\n"
        f"需要翻译的内容：{block.text}\n")
    
    payload = {
        "model": config.model_id,  # 必填参数[^1]
        "messages": [
            {
                "role": "system",
                "content": system_prompt  # 系统指令[^2]
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.3,        # 控制随机性[^4]
        "max_tokens": 1024,        # 支持长上下文[^3]
        "top_p": 0.9,             # 平衡多样性[^4]
        "n": 1,                   # 固定生成数量[^1]
        "frequency_penalty": 0.5   # 减少重复[^4]
    }
    

    max_retries = 5
    for i in range(max_retries):
        try:
            response = requests.post(
                f"{config.api_url}/chat/completions",  # 官方接口路径[^1]
                headers=config.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            # 严格提取翻译结果[^2]
            response_data = response.json()
            raw_text = response_data['choices'][0]['message']['content'].strip()
            return raw_text.split("：")[-1].strip()
        
        except Exception as e:
            print(f"Error translating block {block.index}: {str(e)}")
            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(2)
            else:
                return block.text + " [TRANSLATION_FAILED]"

def translate_block_ollama(
    config: ModelConfigOllama,
    block: SubtitleBlock,
    context: str,
    domain: Optional[str]
) -> str:
    """基于Ollama Chat结构的翻译实现"""
    system_message = (
        f"你是一个资深的{domain or '通用'}领域的字幕翻译专家，严格遵守以下规则：\n"
        "1. 仅输出简体中文译文\n"
        "2. 根据上下文参考给出最符合语境的翻译\n"
        "3. 确保译文语序和表述符合中文正确的语言习惯\n"
        "4. 自动校正原文中可能存在的的拼写错误\n"
        "5. 猜想并保持原始文本的风格和语气\n"
        "6. 专业技术词汇请参考当前领域知识进行翻译\n"
        f"当前领域：{domain or '通用领域'}"
        "请严格按要求输出译文（不要添加任何解释或符号）"
    )
    
    payload = {
        "model": config.model_id,   # 必须指定模型名称[^5]
        "messages": [
            {
                "role": "system",
                "content": system_message  # 通过系统角色传递指令[^5]
            },
            {
                "role": "user",
                "content": f"上下文参考：{context}\n需翻译：{block.text}"
            }
        ],
        "options": {
            "temperature": config.temperature,  # 生成随机性控制[^6]
            "top_p": config.top_p,
            "num_ctx": config.num_ctx
        },
        "stream": False,
        "keep_alive": config.keep_alive  # 模型驻留控制[^5]
    }
    
    for retry in range(3):
        try:
            response = requests.post(
                f"{config.api_url}/api/chat",  # Chat专用接口[^5]
                headers=config.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get("done", True):
                text_with_think=response_data['message']['content'].strip()  # 提取核心响应[^5]
                # remove text between <think> </think> tag
                text = text_with_think.split("</think>")[-1].strip()
                return text


            raise ValueError("未完成完整响应")
            
        except requests.exceptions.RequestException as e:
            print(f"网络错误 {block.index}:{str(e)}")
            time.sleep(2 ** retry)
        except KeyError:
            print(f"异常响应格式:{response.text[:200]}")
            break
            
    return block.text + " [TRANSLATION_FAILED]"

def translate_block(
    config,
    block: SubtitleBlock,
    context: str,
    domain: Optional[str]
) -> str:
    """根据配置选择翻译函数"""
    if isinstance(config, ModelConfigOpenAI):
        return translate_block_openai(config, block, context, domain)
    elif isinstance(config, ModelConfigOllama):
        return translate_block_ollama(config, block, context, domain)

def generate_srt_translation(
    input_path: str,
    output_path: str,
    config: ModelConfigOpenAI,
    domain: Optional[str] = None,
    delay: float = 0.1,
    window_size: int = 20
) -> None:
    """完整的SRT翻译工作流"""
    all_blocks = parse_srt(input_path)
    total_blocks = len(all_blocks)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for idx, block in tqdm(enumerate(all_blocks),total=total_blocks):
            # 获取动态上下文[^3]
            context = get_context_window(all_blocks, idx, window_size)
            
            # 边界处理[^3]
            if idx == 0:
                print(f"Translating first block (Total: {total_blocks})")
            elif idx == total_blocks - 1:
                print(f"Translating final block (Total: {total_blocks})")
                
            translated_text = translate_block(config, block, context, domain)
            
            print(f"Block {block.index}\n原文：{block.text}\n译文：{translated_text}\n")
            # 写入结果
            f.write(f"{block.index}\n{block.timeline}\n{translated_text}\n\n")
            
            time.sleep(delay)  # 防止速率限制

def re_translate_failed_blocks(
    rough_path: str,
    source_path: str,
    output_path: str,
    config: ModelConfigOpenAI,
    domain: Optional[str] = None,
    delay: float = 0.1,
    window_size: int = 20
) -> None:
    """重新翻译失败的字幕块"""
    rough_blocks = parse_srt(rough_path)
    source_blocks = parse_srt(source_path)
    
    dict_id2block = {block.index: block for block in rough_blocks}

    # Find failed blocks in rough_blocks
    failed_blocks = [block for block in rough_blocks if "[TRANSLATION_FAILED]" in block.text]
    print(f"Found {len(failed_blocks)} failed blocks in {rough_path}")

    for failed_block in tqdm(failed_blocks):
        # 获取动态上下文[^3]
        context = get_context_window(source_blocks, failed_block.index, window_size)
        
        translated_text = translate_block(config, failed_block, context, domain)
        
        print(f"Block {failed_block.index}\n原文：{failed_block.text}\n译文：{translated_text}\n")
        
        # replace failed block in rough_blocks with new translation
        id_failed_block = failed_block.index
        dict_id2block[id_failed_block].text = translated_text

        # time.sleep(delay)  # 防止速率限制
   
    with open(output_path, 'w', encoding='utf-8') as f:
        for block in rough_blocks:
            f.write(f"{block.index}\n{block.timeline}\n{block.text}\n\n")
            


if __name__ == "__main__":
    # split long subtitle blocks
    raw_blocks = parse_srt("acis2507\en_raw.srt")
    split_blocks = split_long_subtitle_blocks(raw_blocks, max_length=15)
    save_srt("acis2507\en.srt", split_blocks)

    # # 初始化配置

    # model_config = ModelConfigOpenAI(
    #     api_url="https://ark.cn-beijing.volces.com/api/v3",
    #     api_key="x",  # 请填写自己的API Key
    #     # model_id="Pro/deepseek-ai/DeepSeek-R1"  # 选择指定模型[^1]
    #     model_id="doubao-pro-32k-241215"  # 选择指定模型[^1]
    # )

    model_config = ModelConfigOllama(
        api_url="x",
        model_id="qwq:32b",
        num_ctx=4096,
        temperature=0.3,
        top_p=0.9,
        stream=False,
        keep_alive="10m"
    )
    
    # 执行翻译流程
    generate_srt_translation(
        input_path="acis2507\en.srt",
        output_path="acis2507\ch_rough_db.srt",
        config=model_config,
        domain="民用航空",
        delay=0.0,
        window_size=5
    )

    # 重新翻译失败的字幕块
    re_translate_failed_blocks(
        rough_path="acis2507\ch_rough_db.srt",
        source_path="acis2507\en.srt",
        output_path="acis2507\ch_db.srt",
        config=model_config,
        domain="民用航空",
        delay=0.0,
        window_size=5
    )
    # merge subtitles
    merge_subtitles("acis2507\ch_db.srt", "acis2507\en.srt", "acis2507\merged.srt")

    cmd_merge = CMD_FFMPEG_MERGE_TEMPLATE.format(
        input_path_video="acis2507/acis2507.mp4",
        input_path_srt="acis2507/merged.srt",
        output_path_video="acis2507/acis2507_ch_en.mp4"
    )
    print(cmd_merge)

    cmd_split = CMD_FFMPEG_SPLIT_TEMPLATE.format(
        input_path_video="acis2507/acis2507_ch_en.mp4",
        output_dir="acis2507/"
    )
    print(cmd_split)
    print("All done!")