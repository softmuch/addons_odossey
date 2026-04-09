import ar from './ar.json'
import bg from './bg.json'
import cs from './cs.json'
import de from './de.json'
import en from './en.json'
import fi from './fi.json'
import he from './he.json'
import hr from './hr.json'
import id from './id.json'
import it from './it.json'
import ko from './ko.json'
import pl from './pl.json'
import ro from './ro.json'
import sk from './sk.json'
import sr from './sr.json'
import th from './th.json'
import uk from './uk.json'
import zh from './zh.json'
import az from './az.json'
import bs from './bs.json'
import da from './da.json'
import el from './el.json'
import es from './es.json'
import fr from './fr.json'
import hi from './hi.json'
import hu from './hu.json'
import ja from './ja.json'
import nl from './nl.json'
import pt from './pt.json'
import ru from './ru.json'
import sl from './sl.json'
import sv from './sv.json'
import tr from './tr.json'
import vi from './vi.json'
import { useI18n } from 'vue-i18n'

export const messages = {
  ar,
  bg,
  cs,
  de,
  en,
  fi,
  he,
  hr,
  id,
  it,
  ko,
  pl,
  ro,
  sk,
  sr,
  th,
  uk,
  zh,
  az,
  bs,
  da,
  el,
  es,
  fr,
  hi,
  hu,
  ja,
  nl,
  pt,
  ru,
  sl,
  sv,
  tr,
  vi,
}

type I18n = ReturnType<typeof useI18n<{}>>

let _i18n: I18n | undefined = undefined
export function i18n(): I18n {
  if (!_i18n) {
    // @ts-ignore
    _i18n = useI18n()
    // @ts-ignore
    return _i18n
  }
  return _i18n
}
