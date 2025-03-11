from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SubtitleBlock:
    '''
    字幕块
    Sample:
    1
    00:00:06,460 --> 00:00:07,980
    你做了什么？
    What did you do?
    '''
    def __init__(self, index:int, timeline:str, text:str):
        self.index = index
        self.timeline = timeline
        self.text = text
        self.start = None
        self.end = None
        self.duration = None

    def calc_duration(self) -> float:
        start, end = self.timeline.split(" --> ")
        start = start.split(":")
        end = end.split(":")
        self.start = int(start[0])*3600 + int(start[1])*60 + float(start[2].replace(",","."))
        self.end = int(end[0])*3600 + int(end[1])*60 + float(end[2].replace(",","."))
        self.duration = self.end - self.start

def format_timeline(start: float,end:float) -> str:
    start_str = f"{int(start//3600):02d}:{int((start%3600)//60):02d}:{start%60:.3f}".replace(".",",")
    end_str = f"{int(end//3600):02d}:{int((end%3600)//60):02d}:{end%60:.3f}".replace(".",",")
    return f"{start_str} --> {end_str}"

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

# 拆分过长的字幕block为两段，按照标点或空格分词拆分
def split_long_subtitle_blocks(blocks: List[SubtitleBlock], max_length: int = 15) -> List[SubtitleBlock]:
    new_blocks = []
    index=1
    for block in blocks:
        # count the number of words
        words = block.text.split()
        if len(words) <= max_length:
            new_blocks.append(SubtitleBlock(index=index, timeline=block.timeline, text=block.text))
            index += 1
            continue
        # split the block
        n_blocks= len(words) // max_length
        if len(words) % max_length != 0:
            n_blocks += 1
        target_length = len(words) // n_blocks
        block.calc_duration()
        duration = block.duration
        for i in range(n_blocks):
            new_text = " ".join(words[i*target_length:(i+1)*target_length])
            new_timeline = format_timeline(block.start + i*duration/n_blocks, block.start + (i+1)*duration/n_blocks)
            new_blocks.append(SubtitleBlock(index=index, timeline=new_timeline, text=new_text))
            index += 1
    return new_blocks

def save_srt(file_path: str, blocks: List[SubtitleBlock]):
    """SRT文件保存器"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for block in blocks:
            f.write(f"{block.index}\n{block.timeline}\n{block.text}\n\n")

def merge_subtitles(path_1: str, path_2: str, path_out: str):
    """合并两个SRT字幕文件"""
    
    # load subtitles
    blocks_1 = parse_srt(path_1)
    blocks_1 = {block.index: block for block in blocks_1}
    blocks_2 = parse_srt(path_2)
    blocks_2 = {block.index: block for block in blocks_2}

    # merge subtitles
    new_blocks = []
    ids_1 = sorted(blocks_1.keys())

    for index in ids_1:
        block_1 = blocks_1.get(index,None)
        block_2 = blocks_2.get(index,None)
        text1 = block_1.text if block_1 else ""
        text2 = block_2.text if block_2 else ""
        new_block = SubtitleBlock(index=block_1.index, timeline=block_1.timeline, text=f"{text1}\n{text2}")
        new_blocks.append(new_block)
    # save new subtitles
    save_srt(path_out, new_blocks)

def get_context_window(blocks: List[SubtitleBlock], current_index: int, window_size=50) -> str:
    """获取动态上下文窗口"""
    if not window_size:
        return "<NO_CONTEXT>"
    start = max(0, current_index - window_size)
    end = min(len(blocks), current_index + window_size + 1)
    return " | ".join([block.text for block in blocks[start:end]])

CMD_FFMPEG_MERGE_TEMPLATE = '''ffmpeg -hwaccel cuda -c:v h264_cuvid -i "{input_path_video}" -vf subtitles="{input_path_srt}" -c:v h264_nvenc  -b:v 8000k -c:a copy "{output_path_video}" -y'''
CMD_FFMPEG_SPLIT_TEMPLATE = '''ffmpeg -i "{input_path_video}" -c:v copy -c:a copy -f segment -segment_time 290 -reset_timestamps 1 {output_dir}split_%03d.mp4'''