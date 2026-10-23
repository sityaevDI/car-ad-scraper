import i18n, { intlLocale } from '../i18n'

export function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat(intlLocale()).format(price)} ${currency}`
}

export function formatMileage(km: number): string {
  return `${new Intl.NumberFormat(intlLocale()).format(km)} ${i18n.t('common.km')}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(intlLocale(), { year: 'numeric', month: 'short', day: 'numeric' })
}
