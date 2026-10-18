import type { HorizonState } from '../api/types'
import { STATE } from '../lib/labels'
import { Badge } from './ui'

export function StateBadge({ state }: { state: HorizonState }) {
  const meta = STATE[state]
  return (
    <Badge tone={meta.tone} dot>
      {meta.label}
    </Badge>
  )
}
