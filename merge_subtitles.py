from subtitle import SubtitleBlock, parse_srt, save_srt

# load subtitles
blocks_1 = parse_srt("acis2508/ch.srt")
blocks_1 = {block.index: block for block in blocks_1}
blocks_2 = parse_srt("acis2508/en.srt")
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
save_srt("acis2508/merged.srt", new_blocks)