export function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat('ru-RU').format(price)} ${currency}`
}

export function formatMileage(km: number): string {
  return `${new Intl.NumberFormat('ru-RU').format(km)} км`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { year: 'numeric', month: 'short', day: 'numeric' })
}
