import type { ReactNode } from 'react'

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto mt-16 w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="mb-6 text-xl font-semibold text-slate-900">{title}</h1>
      {children}
    </div>
  )
}

export function FieldLabel({ children, htmlFor }: { children: ReactNode; htmlFor: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-slate-700">
      {children}
    </label>
  )
}

export const inputClass =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500'

export const primaryButtonClass =
  'w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50'

export function ErrorText({ children }: { children: ReactNode }) {
  return <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{children}</p>
}

export function SuccessText({ children }: { children: ReactNode }) {
  return <p className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{children}</p>
}
