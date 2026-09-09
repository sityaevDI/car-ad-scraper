// Canonical values normalized by app/sources/polovniautomobili/mapper.py — kept in sync manually,
// there's no backend endpoint enumerating them (only /vehicles/makes for make/model).
export const FUEL_TYPE_OPTIONS = [
  { value: 'petrol', label: 'Бензин' },
  { value: 'diesel', label: 'Дизель' },
  { value: 'hybrid', label: 'Гибрид' },
  { value: 'electric', label: 'Электро' },
  { value: 'lpg', label: 'Газ (LPG)' },
  { value: 'cng', label: 'Газ (CNG)' },
] as const

export const TRANSMISSION_OPTIONS = [
  { value: 'manual', label: 'Механика' },
  { value: 'automatic', label: 'Автомат' },
] as const

export const BODY_TYPE_OPTIONS = [
  { value: 'sedan', label: 'Седан' },
  { value: 'wagon', label: 'Универсал' },
  { value: 'hatchback', label: 'Хэтчбек' },
  { value: 'suv', label: 'Внедорожник' },
  { value: 'coupe', label: 'Купе' },
  { value: 'convertible', label: 'Кабриолет' },
  { value: 'pickup', label: 'Пикап' },
  { value: 'minivan', label: 'Минивэн' },
] as const

export const PAGE_SIZE = 20
export const DRILL_DOWN_PAGE_SIZE = 10
