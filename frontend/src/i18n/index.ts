import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import ru from './locales/ru.json'

export const SUPPORTED_LANGUAGES = ['ru', 'en'] as const
export type Language = (typeof SUPPORTED_LANGUAGES)[number]

const STORAGE_KEY = 'language'

function isLanguage(value: string | null | undefined): value is Language {
  return SUPPORTED_LANGUAGES.includes(value as Language)
}

function detectLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch {
    // localStorage may be unavailable (private mode); fall through to browser language
  }
  return navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

export function setLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // ignore: the choice just won't persist
  }
  void i18n.changeLanguage(language)
}

export function intlLocale(): string {
  return i18n.language === 'en' ? 'en-US' : 'ru-RU'
}

i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
})

void i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, en: { translation: en } },
  lng: detectLanguage(),
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

export default i18n

export type OptionGroup =
  | 'fuel_type'
  | 'transmission'
  | 'body_type'
  | 'interior_material'
  | 'air_condition'
  | 'drive_type'
  | 'seats'

// Falls back to the raw value for canonical values the dictionaries don't know yet.
export function optionLabel(group: OptionGroup, value: string): string {
  return i18n.t(`options.${group}.${value}`, { defaultValue: value })
}

export function equipmentLabel(value: string): string {
  return i18n.t(`equipment.${value}`, { defaultValue: value })
}
