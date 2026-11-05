import { useEffect, useState } from 'react'
import { accountApi, ApiError } from '../api/quizApi'
import type { CoachResponse, RecommendationsResponse, User, UserStats } from '../api/types'
import './Account.css'

export function StatsScreen({ user, onBack }: { user: User; onBack: () => void }) {
  const [stats, setStats] = useState<UserStats | null>(null)
  const [coach, setCoach] = useState<CoachResponse | null>(null)
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [coachLoading, setCoachLoading] = useState(false)
  const [recommendationsLoading, setRecommendationsLoading] = useState(false)
  useEffect(() => { accountApi.stats().then(setStats).catch(error => setError(error instanceof ApiError ? error.message : 'Could not load statistics.')) }, [])
  const requestCoach = async () => {
    setCoachLoading(true); setError(null)
    try { setCoach(await accountApi.coach()) } catch (error) { setError(error instanceof ApiError ? error.message : 'Coach unavailable.') } finally { setCoachLoading(false) }
  }
  const requestRecommendations = async () => {
    setRecommendationsLoading(true); setError(null)
    try { setRecommendations(await accountApi.recommendations()) } catch (error) { setError(error instanceof ApiError ? error.message : 'Recommendations unavailable.') } finally { setRecommendationsLoading(false) }
  }
  return <section className="stats-shell"><nav className="account-nav"><strong>CineQuote <span>Play</span></strong><button onClick={onBack}>Back to cinema</button></nav>
    <header className="stats-head"><div><p className="quiz-kicker">Player dossier</p><h1>{user.username}'s stats</h1></div><p>Your completed signed-in games appear here.</p></header>
    {error && <p className="account-error">{error}</p>}
    {!stats ? <p>Loading the archive…</p> : <>
      <div className="coach-card"><div><span>Your next challenge</span><h2>Your next screening, chosen from real results.</h2></div><button className="primary-action" disabled={coachLoading} onClick={() => void requestCoach()}>{coachLoading ? 'Building…' : coach ? 'Refresh challenge' : 'Choose my next game'}</button>{coach && <div className="coach-note"><p>{coach.summary}</p><small>Strength: {coach.strength} · Focus: {coach.improvement} · Next: {coach.recommended_genre} {coach.recommended_difficulty}</small></div>}</div>
      <section className="recommendation-card"><div className="recommendation-heading"><div><span>Curated from your results</span><h2>What to watch next</h2></div><button className="primary-action" disabled={recommendationsLoading} onClick={() => void requestRecommendations()}>{recommendationsLoading ? 'Curating…' : recommendations ? 'Refresh picks' : 'Recommend films'}</button></div>
        {recommendations ? <><p className="recommendation-intro">{recommendations.intro}</p><div className="film-picks">{recommendations.recommendations.map((film, index) => <article key={film.title}><small>Missed film {String(index + 1).padStart(2, '0')}</small><h3>{film.title}</h3><p className="film-summary">{film.summary}</p><p>{film.reason}</p><div>{film.genres.join(' · ') || 'Catalog selection'}</div>{film.source_url && <a className="synopsis-source" href={film.source_url} target="_blank" rel="noreferrer">Source: Wikipedia</a>}</article>)}</div>{recommendations.recommendations.length === 0 && <p className="account-note">Perfect latest game: there is nothing to review.</p>}<p className="recommendation-meta">Based on your latest saved game{recommendations.fallback_used ? ' · synopsis withheld by spoiler guard' : ' · source-based spoiler-free synopsis'}</p></> : <p className="account-note">After your next signed-in game, every film you miss will appear here with a source-based, spoiler-guarded synopsis.</p>}
      </section>
      <div className="stats-grid"><Stat label="Games" value={stats.games_played}/><Stat label="Average" value={`${stats.average_percentage}%`}/><Stat label="Best score" value={`${stats.best_percentage}%`}/><Stat label="Hints used" value={stats.hints_used}/></div>
      <div className="stats-columns"><Breakdown title="By genre" rows={stats.by_genre}/><Breakdown title="By difficulty" rows={stats.by_difficulty}/></div>
      <section className="stats-panel" style={{marginTop:'1rem'}}><h2>Recent screenings</h2>{stats.recent_attempts.length === 0 ? <p className="account-note">Complete a quiz while signed in to start your history.</p> : stats.recent_attempts.map((attempt,index) => <div className="attempt-row" key={`${attempt.completed_at}-${index}`}><span>{attempt.genre.replace('_',' ')}</span><span>{attempt.difficulty}</span><strong>{attempt.score}/{attempt.total_questions}</strong><span>{attempt.percentage}%</span></div>)}</section>
    </>}
  </section>
}
function Stat({label,value}:{label:string;value:string|number}) { return <div className="stat-card"><span>{label}</span><strong>{value}</strong></div> }
function Breakdown({title,rows}:{title:string;rows:UserStats['by_genre']}) { return <section className="stats-panel"><h2>{title}</h2>{rows.length === 0 ? <p className="account-note">No data yet.</p> : rows.map(row => <div className="breakdown-row" key={row.label}><span>{row.label.replace('_',' ')}</span><span>{row.games_played} games</span><strong>{row.average_percentage}%</strong></div>)}</section> }
