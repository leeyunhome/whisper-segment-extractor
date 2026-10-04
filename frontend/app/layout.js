import './globals.css'

export const metadata = {
  title: 'EBS 왕초보 영어 - AI 학습 플레이어',
  description: 'AI가 추출한 원어민 대화로 영어 실력을 쑥쑥!',
}

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        {children}
      </body>
    </html>
  )
}
