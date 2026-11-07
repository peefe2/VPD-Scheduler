// 서비스 마크: 잎 모양 안의 물방울(공기 중 수분). 사이드바·소개·로그인 화면에서 같이 쓴다.
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4cc28f" />
          <stop offset="1" stopColor="#0d6148" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#logo-g)" />
      <path d="M16 6.5c3.6 4.3 6.5 8 6.5 11.6a6.5 6.5 0 0 1-13 0c0-3.6 2.9-7.3 6.5-11.6Z" fill="#fff" opacity="0.95" />
      <path d="M13.2 18.6a3 3 0 0 0 2.8 2.9" stroke="#138a63" strokeWidth="1.6" strokeLinecap="round" fill="none" />
    </svg>
  )
}
