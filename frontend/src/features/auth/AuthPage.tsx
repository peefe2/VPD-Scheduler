import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useLogin, useMe, useSignup } from '../../api/hooks'
import { hintClass, inputClass } from '../../components/classes'
import { Button, Card, ErrorState, Field, Loading, PageHeader } from '../../components/ui'

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
    <>
      <PageHeader
        title={signup ? '회원가입' : '로그인'}
        sub={signup ? '이메일로 가입하면 내 온실을 만들고 관리할 수 있습니다.' : '내 온실을 보려면 로그인하세요.'}
      />
      <div style={{ maxWidth: 440 }}>
        <Card title={signup ? '새 계정' : '계정'}>
          <form onSubmit={submit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Field label="이메일" htmlFor="auth-email">
              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                className={inputClass}
                value={email}
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
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </Field>
            )}
            {action.error && <ErrorState error={action.error} />}
            <Button type="submit" disabled={action.isPending}>
              {action.isPending ? '확인 중…' : signup ? '가입하기' : '로그인'}
            </Button>
            <p className={hintClass}>
              {signup ? (
                <>
                  이미 계정이 있나요? <Link to="/login">로그인</Link>
                </>
              ) : (
                <>
                  처음이신가요? <Link to="/signup">회원가입</Link> · 로그인하지 않아도 공개 데모 온실은 볼 수 있습니다.
                </>
              )}
            </p>
            {signup && (
              <p className={hintClass}>
                이메일 확인 메일은 보내지 않고, 비밀번호 찾기 기능은 아직 없습니다. 비밀번호를 잊지 않게 해 주세요.
              </p>
            )}
          </form>
        </Card>
      </div>
    </>
  )
}
