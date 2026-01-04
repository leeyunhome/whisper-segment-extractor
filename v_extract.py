import json
import sys

def analyze_transcription(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data['segments']
    anchor_phrases = ["전체대화 주세요", "전체대화", "전체 대화", "전체되어", "전체 되어"]
    
    anchor_found = None
    anchor_idx = -1
    for i, seg in enumerate(segments):
        text = seg['text'].strip()
        for anchor in anchor_phrases:
            if anchor in text:
                anchor_found = seg
                anchor_idx = i
                break
        if anchor_found:
            break
            
    debug_info = {
        "anchor": None,
        "segments_after": [],
        "teacher_start": None,
        "all_segments_near_anchor": []
    }

    if anchor_found:
        debug_info["anchor"] = {
            "idx": anchor_idx,
            "text": anchor_found['text'],
            "start": anchor_found['start'],
            "end": anchor_found['end']
        }
        
        for i in range(max(0, anchor_idx - 5), min(len(segments), anchor_idx + 20)):
            seg = segments[i]
            debug_info["all_segments_near_anchor"].append({
                "idx": i,
                "start": seg['start'],
                "end": seg['end'],
                "text": seg['text']
            })
            
        anchor_end_time = anchor_found['end']
        korean_segments_after_anchor = []
        for i in range(anchor_idx + 1, len(segments)):
            seg = segments[i]
            if seg['start'] > anchor_end_time + 5:
                korean_segments_after_anchor.append(seg)
        
        for i in range(len(korean_segments_after_anchor) - 2):
            seg1 = korean_segments_after_anchor[i]
            seg2 = korean_segments_after_anchor[i+1]
            seg3 = korean_segments_after_anchor[i+2]
            
            gap1 = seg2['start'] - seg1['start']
            gap2 = seg3['start'] - seg2['start']
            
            if gap1 <= 5.0 and gap2 <= 5.0:
                debug_info["teacher_start"] = {
                    "time": seg1['start'],
                    "gap1": gap1,
                    "gap2": gap2,
                    "seg1": seg1['text'],
                    "seg2": seg2['text'],
                    "seg3": seg3['text']
                }
                break

    with open('debug_out.json', 'w', encoding='utf-8') as f:
        json.dump(debug_info, f, ensure_ascii=False, indent=2)

analyze_transcription('transcription_20260101_173000_2658e4d8_mp3.json')
