import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold tracking-[0.01em] transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-blue-700/60 bg-primary text-primary-foreground shadow-sm hover:bg-primary/80',
        secondary:
          'border-blue-200/80 bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive:
          'border-red-700/50 bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        outline: 'bg-background/55 text-foreground shadow-[0_1px_0_rgba(255,255,255,0.72)_inset]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants }
