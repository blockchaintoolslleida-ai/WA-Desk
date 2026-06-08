import { createContext, useContext, useState } from 'react';
import translations from '../lib/i18n';

const LanguageContext = createContext(null);

const LANG_LOCALES = { ca: 'ca-ES', es: 'es-ES', en: 'en-US' };

export const LanguageProvider = ({ children }) => {
  const [language, setLanguage] = useState(() => localStorage.getItem('wa_desk_lang') || 'ca');

  const changeLanguage = (lang) => {
    setLanguage(lang);
    localStorage.setItem('wa_desk_lang', lang);
  };

  const locale = LANG_LOCALES[language] || 'ca-ES';

  const t = (key, vars) => {
    let text = translations[language]?.[key] || translations['ca']?.[key] || key;
    if (vars) Object.entries(vars).forEach(([k, v]) => { text = text.replace(`{${k}}`, v); });
    return text;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage: changeLanguage, t, locale }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useTranslation must be used within LanguageProvider');
  return context;
};

export default LanguageContext;
