import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'border border-blue-700/70 bg-primary text-primary-foreground shadow-[0_1px_0_rgba(255,255,255,0.35)_inset,0_8px_20px_rgba(37,83,176,0.16)] hover:bg-primary/90 hover:shadow-[0_0_0_1px_rgba(77,132,255,0.28),0_10px_24px_rgba(37,83,176,0.2)]',
        destructive:
          'border border-red-700/50 bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline:
          'border border-input bg-background/70 shadow-[0_1px_0_rgba(255,255,255,0.8)_inset] hover:border-blue-300 hover:bg-blue-50/70 hover:text-blue-900',
        secondary:
          'border border-blue-200/70 bg-secondary text-secondary-foreground hover:border-blue-300 hover:bg-secondary/80',
        ghost: 'hover:bg-blue-50/70 hover:text-blue-900',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-8',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
