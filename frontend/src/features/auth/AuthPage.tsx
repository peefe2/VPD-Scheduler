import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useLogin, useMe, useSignup } from '../../api/hooks'
import { inputClass } from '../../components/classes'
import { LogoMark } from '../../components/Logo'
import { Button, ErrorState, Field, Loading } from '../../components/ui'
import s from './auth.module.css'

const POINTS = [
  { title: '하루 단위로 돌아보기', desc: '날마다 낮 시간 중 적정 대역 안에 있던 비율을 캘린더 색으로 봅니다.' },
  { title: '검증된 예측만', desc: '이 온실 실측으로 현재 값보다 낫다고 확인된 뒤에만 1·3시간 뒤를 예측합니다.' },
  { title: '결정은 사람이', desc: '등록한 설비 안에서 조치 후보를 보여줄 뿐, 설비를 자동으로 움직이지 않습니다.' },
]

// 이메일 인증은 하지 않는다 — 이메일은 아이디로만 쓴다 (결정 2026-11-01)
export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const { data: me, isLoading } = useMe()
  const login = useLogin()
  const create = useSignup()
  const action = signup ? create : login
  const navigate = useNavigate()

  if (isLoading) return <Loading />
  if (me) return <Navigate to="/" replace />

  const tooShort = signup && password.length < 8
  const mismatch = signup && password !== confirm
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (!email.trim() || !password || tooShort || mismatch) return
    action.mutate({ email: email.trim(), password }, { onSuccess: () => navigate('/', { replace: true }) })
  }

  return (
    <div className={s.page}>
      <aside className={s.panel}>
        <Link to="/about" className={s.brand}>
          <LogoMark size={32} />
          VPD 캘린더
        </Link>
        <div>
          <h2 className={s.pitchTitle}>
            온실의 공기를
            <br />
            하루 단위로 읽습니다
          </h2>
          <ul className={s.points}>
            {POINTS.map((p) => (
              <li key={p.title}>
                <span className={s.check} aria-hidden="true" />
                <span>
                  <strong>{p.title}</strong>
                  {p.desc}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className={s.panelFoot}>2026 이매지니어 프로젝트 · 씩씩이들</p>
      </aside>

      <main className={s.formSide}>
        <div className={s.formBox}>
          <Link to="/about" className={s.mobileBrand}>
            <LogoMark size={28} />
            VPD 캘린더
          </Link>
          <h1 className={s.title}>{signup ? '계정 만들기' : '다시 오신 걸 환영합니다'}</h1>
          <p className={s.sub}>
            {signup ? '이메일로 가입하면 내 온실을 등록하고 관리할 수 있습니다.' : '내 온실을 보려면 로그인하세요.'}
          </p>

          <form onSubmit={submit} noValidate className={s.form}>
            <Field label="이메일" htmlFor="auth-email">
              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                placeholder="name@example.com"
                className={inputClass}
                value={email}
                aria-invalid={submitted && !email.trim()}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field
              label="비밀번호"
              htmlFor="auth-password"
              hint={signup ? (submitted && tooShort ? '8자 이상이어야 합니다.' : '8자 이상') : undefined}
            >
              <input
                id="auth-password"
                type="password"
                autoComplete={signup ? 'new-password' : 'current-password'}
                className={inputClass}
                value={password}
                aria-invalid={submitted && (!password || tooShort)}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            {signup && (
              <Field
                label="비밀번호 확인"
                htmlFor="auth-confirm"
                hint={submitted && mismatch ? '비밀번호가 서로 다릅니다.' : undefined}
              >
                <input
                  id="auth-confirm"
                  type="password"
                  autoComplete="new-password"
                  className={inputClass}
                  value={confirm}
                  aria-invalid={submitted && mismatch}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </Field>
            )}
            {action.error && <ErrorState error={action.error} />}
            <Button type="submit" disabled={action.isPending}>
              {action.isPending ? '확인 중…' : signup ? '가입하기' : '로그인'}
            </Button>
          </form>

          <p className={s.switch}>
            {signup ? (
              <>
                이미 계정이 있나요? <Link to="/login">로그인</Link>
              </>
            ) : (
              <>
                처음이신가요? <Link to="/signup">회원가입</Link>
              </>
            )}
          </p>
          <div className={s.divider}>
            <span>또는</span>
          </div>
          <Link to="/" className={s.demo}>
            로그인 없이 공개 데모 온실 둘러보기 →
          </Link>
          {signup && (
            <p className={s.note}>
              이메일 확인 메일은 보내지 않고, 비밀번호 찾기 기능은 아직 없습니다. 비밀번호를 잊지 않게 해 주세요.
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
