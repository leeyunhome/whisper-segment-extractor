'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import Link from 'next/link'

const CATEGORY_COLORS = {
  '여행': 'var(--tag-여행)',
  '일상': 'var(--tag-일상)',
  '직업': 'var(--tag-직업)',
  '관계': 'var(--tag-관계)',
  '가정': 'var(--tag-가정)',
}

export default function Home() {
  const [episodes, setEpisodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState('')

  useEffect(() => {
    async function fetchEpisodes() {
      const { data, error } = await supabase
        .from('episodes')
        .select('*')
        .order('episode_num', { ascending: false })
      
      if (error) {
        console.error('Error fetching episodes:', error)
      } else {
        setEpisodes(data)
      }
      setLoading(false)
    }

    fetchEpisodes()
  }, [])

  const categories = [...new Set(episodes.map(e => e.category).filter(Boolean))].sort()

  const filteredEpisodes = episodes.filter(ep => {
    const haystack = `${ep.episode_num} ${ep.subtitle} ${ep.category}`.toLowerCase()
    const matchesSearch = haystack.includes(search.toLowerCase())
    const matchesCategory = activeCategory ? ep.category === activeCategory : true
    return matchesSearch && matchesCategory
  })

  // localStorage에서 재생 횟수 가져오기 (Claude 방식)
  function getPlayCount(stem) {
    try {
      const key = 'ebs_played_' + stem
      const data = JSON.parse(localStorage.getItem(key) || '{}')
      return data.play_count || 0
    } catch (e) { return 0 }
  }

  return (
    <div className="container">
      <header>
        <h1>🎧 EBS 왕초보 영어</h1>
        <div className="header-subtitle">
          총 {episodes.length}개 회차 · AI 자동 추출 플레이어
        </div>
      </header>

      <div className="dashboard-controls">
        <input 
          className="search" 
          placeholder="회차 번호 또는 제목 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-tags">
          <button 
            className={`tag-btn ${activeCategory === '' ? 'active' : ''}`}
            onClick={() => setActiveCategory('')}
          >
            전체
          </button>
          {categories.map(cat => (
            <button 
              key={cat}
              className={`tag-btn ${activeCategory === cat ? 'active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="stats">
        필터 결과: <strong>{filteredEpisodes.length}</strong>개
      </div>

      {loading ? (
        <div className="grid">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="card" style={{ height: '140px', opacity: 0.5 }}>로딩 중...</div>
          ))}
        </div>
      ) : (
        <div className="grid">
          {filteredEpisodes.map(ep => {
            // mp3_path에서 stem 추출 (예: episodes/2707_20260501.mp3 -> 2707_여행_... 형태의 stem이 필요하지만, 
            // 여기서는 DB의 metadata를 활용하거나 mp3_path 기반으로 매칭)
            const stem = ep.metadata?.original_filename?.replace('.mp3', '') || ep.mp3_path.split('/').pop().replace('.mp3', '')
            const playCount = getPlayCount(stem)
            const tagColor = CATEGORY_COLORS[ep.category] || 'var(--accent)'
            
            return (
              <Link href={`/episode/${ep.id}`} key={ep.id} className="card">
                {playCount > 0 && <div className="card-played">▶ {playCount}회</div>}
                <span className="card-tag" style={{ backgroundColor: tagColor }}>{ep.category}</span>
                <div className="card-ep">EP {ep.episode_num}</div>
                <div className="card-title">{ep.subtitle}</div>
                <div className="card-meta">
                  <span>{ep.air_date}</span>
                  <span>
                    {Math.floor(ep.duration_sec / 60)}분 {Math.floor(ep.duration_sec % 60)}초 · {ep.script_count}문장
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {!loading && filteredEpisodes.length === 0 && (
        <div className="empty">검색 결과가 없습니다</div>
      )}
    </div>
  )
}
