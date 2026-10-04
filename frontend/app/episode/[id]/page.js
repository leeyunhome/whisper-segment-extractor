'use client'

import { useEffect, useState, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { useParams, useRouter } from 'next/navigation'

export default function EpisodeDetail() {
  const { id } = useParams()
  const router = useRouter()

  // Data State
  const [episode, setEpisode] = useState(null)
  const [scripts, setScripts] = useState([])
  const [loading, setLoading] = useState(true)
  const [audioUrl, setAudioUrl] = useState('')

  // Player State
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(-1)
  const [repeatMode, setRepeatMode] = useState(false)
  const [autoNextMode, setAutoNextMode] = useState(false)
  const [showSubtitles, setShowSubtitles] = useState(true)
  const [playbackRate, setPlaybackRate] = useState(1)

  const audioRef = useRef(null)
  const linesRef = useRef([])

  useEffect(() => {
    async function fetchData() {
      const { data: epData, error: epError } = await supabase
        .from('episodes')
        .select('*')
        .eq('id', id)
        .single()

      if (epError) return
      setEpisode(epData)

      const { data: storageData } = supabase.storage
        .from('episodes')
        .getPublicUrl(epData.mp3_path)
      setAudioUrl(storageData.publicUrl)

      const { data: scriptData } = await supabase
        .from('scripts')
        .select('*')
        .eq('episode_id', id)
        .order('seq', { ascending: true })

      if (scriptData) setScripts(scriptData)
      setLoading(false)
    }
    if (id) fetchData()
  }, [id])

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      if (e.key === ' ') {
        e.preventDefault()
        if (audioRef.current.paused) audioRef.current.play(); else audioRef.current.pause()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        if (currentIndex > 0) playLine(currentIndex - 1); else playLine(0)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        if (currentIndex < scripts.length - 1) playLine(currentIndex + 1)
      } else if (e.key.toLowerCase() === 'r') {
        setRepeatMode(prev => !prev)
      } else if (e.key.toLowerCase() === 's') {
        setShowSubtitles(prev => !prev)
      } else if (e.key.toLowerCase() === 'a') {
        setAutoNextMode(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentIndex, scripts])

  const playLine = (idx) => {
    if (idx < 0 || idx >= scripts.length) return
    const line = scripts[idx]
    audioRef.current.currentTime = line.start_sec
    audioRef.current.play()
    setCurrentIndex(idx)
  }

  const handleTimeUpdate = () => {
    const t = audioRef.current.currentTime

    // Find current index
    let idx = -1
    for (let i = 0; i < scripts.length; i++) {
      if (t >= scripts[i].start_sec && t < scripts[i].end_sec) {
        idx = i
        break
      }
    }
    if (idx === -1) {
      for (let i = scripts.length - 1; i >= 0; i--) {
        if (t >= scripts[i].start_sec) {
          idx = i
          break
        }
      }
    }

    // Repeat Mode
    if (repeatMode && currentIndex >= 0) {
      if (t >= scripts[currentIndex].end_sec) {
        audioRef.current.currentTime = scripts[currentIndex].start_sec
        return
      }
    }

    // Auto Next
    if (autoNextMode && !repeatMode && currentIndex >= 0 && currentIndex < scripts.length - 1) {
      if (t >= scripts[currentIndex].end_sec + 0.1) {
        const next = scripts[currentIndex + 1]
        if (t < next.start_sec - 1) {
          audioRef.current.currentTime = next.start_sec
        }
      }
    }

    if (idx !== currentIndex) {
      setCurrentIndex(idx)
      // Scroll to active line
      const el = document.getElementById(`line-${idx}`)
      if (el) {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }
    }
  }

  // 학습 기록 저장 (Claude 방식)
  const handlePlay = () => {
    setIsPlaying(true)
    try {
      const stem = episode.metadata?.original_filename?.replace('.mp3', '') || episode.mp3_path.split('/').pop().replace('.mp3', '')
      const key = 'ebs_played_' + stem
      const data = JSON.parse(localStorage.getItem(key) || '{}')
      data.last_played = new Date().toISOString()
      data.play_count = (data.play_count || 0) + 1
      localStorage.setItem(key, JSON.stringify(data))
    } catch (e) { }
  }

  if (loading) return <div className="container">로딩 중...</div>

  return (
    <div className={showSubtitles ? "" : "subtitles-hidden"}>
      <div className="player-container">
        {/* 좌측: 컨트롤 */}
        <div className="player-controls">
          <button onClick={() => router.push('/')} className="back-link">← 전체 목록</button>
          <div className="player-ep-num">EP {episode.episode_num} · {episode.category}</div>
          <h1 className="player-title">{episode.subtitle}</h1>
          <div className="player-meta">
            {episode.air_date} · {Math.floor(episode.duration_sec / 60)}분 {Math.floor(episode.duration_sec % 60)}초
          </div>

          <div className="audio-wrap">
            <audio
              ref={audioRef}
              src={audioUrl}
              controls
              onTimeUpdate={handleTimeUpdate}
              onPlay={handlePlay}
              onPause={() => setIsPlaying(false)}
            />
          </div>

          <div className="btn-row">
            <button
              className={`action ${showSubtitles ? 'active' : ''}`}
              onClick={() => setShowSubtitles(!showSubtitles)}
            >
              👁️ 자막
            </button>
            <button
              className={`action ${repeatMode ? 'active' : ''}`}
              onClick={() => setRepeatMode(!repeatMode)}
            >
              🔁 반복
            </button>
            <button
              className={`action ${autoNextMode ? 'active' : ''}`}
              onClick={() => setAutoNextMode(!autoNextMode)}
            >
              ⏭️ 자동
            </button>
          </div>

          <div className="speed-row">
            {[0.5, 0.75, 1.0, 1.25, 1.5].map(speed => (
              <button
                key={speed}
                className={`speed ${playbackRate === speed ? 'active' : ''}`}
                onClick={() => {
                  setPlaybackRate(speed)
                  audioRef.current.playbackRate = speed
                }}
              >
                {speed}x
              </button>
            ))}
          </div>

          <div className="player-help">
            <kbd>Space</kbd> 재생/정지<br />
            <kbd>←</kbd> <kbd>→</kbd> 이전/다음 문장<br />
            <kbd>R</kbd> 현재 문장 반복 토글<br />
            <kbd>S</kbd> 자막 토글<br />
            <kbd>A</kbd> 자동 다음 토글
          </div>
        </div>

        {/* 우측: 자막 */}
        <div className="subtitles">
          <div className="sub-header">
            <div className="sub-title">대화 스크립트 ({scripts.length}문장)</div>
          </div>
          <div id="lines">
            {scripts.map((s, idx) => (
              <div
                key={s.id}
                id={`line-${idx}`}
                className={`line ${currentIndex === idx ? 'current' : ''} ${repeatMode && currentIndex === idx ? 'repeat-active' : ''}`}
                onClick={() => playLine(idx)}
              >
                <div className="line-time">{s.start_sec.toFixed(2)}s - {s.end_sec.toFixed(2)}s</div>
                <div className="line-text">{s.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
