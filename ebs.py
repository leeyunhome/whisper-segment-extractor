from pydub import AudioSegment

# 1. 파일 불러오기
file_path = "./source_mp3/20260107_173000_fca95311_mp3.mp3" 
audio = AudioSegment.from_mp3(file_path)

# 2. 시간 설정 (밀리초 단위)
# 시작: 24분 56초
start_time = (22 * 60 + 54) * 1000  
# 끝: 25분 41초
end_time = (23 * 60 + 39) * 1000    

# 3. 구간 자르기
extracted_segment = audio[start_time:end_time]

# 4. 파일 저장하기
extracted_segment.export("./extracted_mp3/20260107_173000_fca95311_mp3.mp3", format="mp3")

print("파일 추출 완료: file.mp3 (길이: 45초)")