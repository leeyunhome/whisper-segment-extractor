from pydub import AudioSegment

# 1. 파일 불러오기
file_path = "20251224_173000_b21928fa_mp3.mp3" 
audio = AudioSegment.from_mp3(file_path)

# 2. 시간 설정 (밀리초 단위)
# 시작: 24분 56초
start_time = (23 * 60 + 56) * 1000  
# 끝: 25분 41초
end_time = (24 * 60 + 45) * 1000    

# 3. 구간 자르기
extracted_segment = audio[start_time:end_time]

# 4. 파일 저장하기
extracted_segment.export("extracted_2456_2541.mp3", format="mp3")

print("파일 추출 완료: extracted_2456_2541.mp3 (길이: 45초)")