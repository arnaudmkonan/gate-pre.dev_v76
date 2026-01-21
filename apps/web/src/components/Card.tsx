import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
}

export const Card = ({ children, className = '' }: CardProps) => (
  <div className={`rounded-lg border border-gray-200 bg-white shadow-sm ${className}`}>
    {children}
  </div>
)

export const CardHeader = ({ children, className = '' }: CardProps) => (
  <div className={`border-b border-gray-200 px-6 py-4 ${className}`}>
    {children}
  </div>
)

export const CardTitle = ({ children, className = '' }: CardProps) => (
  <h2 className={`text-lg font-semibold text-gray-900 ${className}`}>
    {children}
  </h2>
)

export const CardDescription = ({ children, className = '' }: CardProps) => (
  <p className={`text-sm text-gray-500 ${className}`}>
    {children}
  </p>
)

export const CardContent = ({ children, className = '' }: CardProps) => (
  <div className={`px-6 py-4 ${className}`}>
    {children}
  </div>
)

export const CardFooter = ({ children, className = '' }: CardProps) => (
  <div className={`border-t border-gray-200 px-6 py-4 ${className}`}>
    {children}
  </div>
)
