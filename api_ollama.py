import time
from dataclasses import dataclass
from typing import List, Optional
import requests

from subtitle import SubtitleBlock

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

def translate_block_ollama(
    config: ModelConfigOllama,
    block: SubtitleBlock,
    context: str,
    domain: Optional[str]
) -> str:
    """基于Ollama Chat结构的翻译实现"""
    system_message = (
    f"您正在执行专业的{domain or '通用领域'}字幕翻译任务，严格遵循：\n"
    "1. 输出纯简体中文（无说明性文字/符号）\n"
    "2. 自动修正原文拼写错误\n"
    "3. 保持时态、专业术语一致性\n"
    "4. 精确匹配语境风格（正式、休闲等）\n\n"
    "【必选步骤】处理流程：\n"
    "A. 分析上下文关系 -> B. 精准直译 -> C. 口语化润色 -> D. 输出译文\n\n"
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
