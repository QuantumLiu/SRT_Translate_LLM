
# 字幕翻译工具 LLM Translator

智能字幕翻译工具，支持OpenAI兼容接口和Ollama本地模型，提供上下文感知的翻译能力。可自动处理SRT格式文件，保留时间轴和序号。
**本程序和文档大部分都由DeepSeek-R1自动化生成**

## 功能特性

- ✅ 支持深言SeekAPI、Ollama等主流LLM服务
- 🌐 内置动态上下文窗口（前N句+后N句）
- 🔄 翻译失败自动重试机制
- 🎯 领域自适应（技术文档/影视剧等场景优化）
- 🧩 模块化设计，易于扩展新模型

## 安装依赖

```bash
pip install requests tqdm requests
```

## 快速开始

### 基础用法（OpenAI兼容接口）
```python
from translate_llm import *

# 初始化配置
config = ModelConfigOpenAI(
    api_key="your_api_key",
    model_id="deepseek-ai/DeepSeek-V3",
    api_url="https://api.siliconflow.cn/v1"
)

# 启动翻译流程
generate_srt_translation(
    input_path="input.srt",
    output_path="output.srt",
    config=config,
    domain="科技文献"  # 领域定制
)
```

### Ollama本地模型
```python
config = ModelConfigOllama(
    model_id="deepseek-r1:32b",
    api_url="http://localhost:11434",
    num_ctx=4096  # 上下文长度
)

generate_srt_translation(
    input_path="movie.srt",
    output_path="movie_cn.srt",
    config=config,
    delay=0.3  # 请求间隔
    domain="科技文献"  # 领域定制
)
```

## 高级用法

### 重试失败翻译
```python
re_translate_failed_blocks(
    rough_path="draft.srt",
    source_path="source.srt",
    output_path="final.srt",
    config=model_config,
    domain="生物医学"
)
```

### 合并双语字幕
使用配套脚本生成双语对照字幕：
```bash
python merge_subtitles.py 
```

## 配置参数说明

### OpenAI配置
```python
@dataclass
class ModelConfigOpenAI:
    api_url: str = "https://api.siliconflow.cn/v1"  # 服务端点
    model_id: str = "deepseek-ai/DeepSeek-V3"        # 模型标识
    api_key: str = "YOUR_API_KEY"                   # 鉴权密钥
```

### Ollama配置
```python
@dataclass
class ModelConfigOllama:
    api_url: str = "http://localhost:11434"    # 本地服务地址
    model_id: str = "llama3.2"                 # 本地模型名称
    num_ctx: int = 4096                        # 上下文长度
    temperature: float = 0.3                   # 随机性控制（0-1）
    keep_alive: str = "5m"                     # 模型驻留时间
```

## 工作原理

1. **上下文感知**：动态组合±N句的上下文数据
2. **领域优化**：通过system prompt注入领域知识
3. **质量增强**：
   - 自动术语保留
   - 句式结构优化
   - 拼写错误纠正
4. **失败处理**：
   - 指数退避重试（5次/3次）
   - 失败标记保留([TRANSLATION_FAILED])

## 注意事项

⚠️ **网络要求**：
- API服务需能访问对应端点

💡 **最佳实践**：
- 首次运行建议小文件测试
- 保持API请求间隔≥0.3秒

📝 **字幕格式**：
- 标准SRT格式文件
- 编码推荐UTF-8
- 单句长度建议≤512字符

**第三方工具推荐**：
- 视频分离和压制[FFmpeg](https://ffmpeg.org/)
- 提取字幕[VoiceTransl](https://github.com/shinnpuru/VoiceTransl)

## 许可证
Apache-2.0 License