import { useTranslation } from 'react-i18next'
import { SUPPORTED_LANGUAGES, setLanguage } from '../i18n'

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  return (
    <div role="group" aria-label={t('nav.language')} className="flex overflow-hidden rounded-md border border-slate-300 text-xs font-medium">
      {SUPPORTED_LANGUAGES.map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => setLanguage(lang)}
          aria-pressed={i18n.language === lang}
          className={
            i18n.language === lang ? 'bg-slate-900 px-2 py-1 text-white' : 'px-2 py-1 text-slate-700 hover:bg-slate-100'
          }
        >
          {lang.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
