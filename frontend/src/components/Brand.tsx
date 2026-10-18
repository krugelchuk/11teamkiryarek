export default function Brand({ large = false }: { large?: boolean }) {
  return <div className={`brand ${large ? 'brand-lg' : ''}`}>
    <img className="brand-logo" src="/brand/janapost-logo.svg" alt="Jańa Post" width="77" height="40" />
    <span className="brand-divider" aria-hidden="true" />
    <span className="brand-copy"><strong>Qadam<span className="brand-team">11</span></strong><span>Кабинет сотрудника</span></span>
  </div>;
}
