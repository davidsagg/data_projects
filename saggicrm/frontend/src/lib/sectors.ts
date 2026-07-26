export const SECTORS = [
  'Tecnologia / Software',
  'Saúde',
  'Consultoria',
  'Serviços Financeiros',
  'Indústria / Manufatura',
  'Varejo / Consumo',
  'Educação',
  'Governo / Setor Público',
  'ONG / Terceiro Setor',
  'Energia / Utilities',
  'Telecomunicações',
  'Mídia / Entretenimento',
  'Agronegócio',
  'Jurídico',
  'RH / Recrutamento',
  'Outro',
] as const

export type Sector = (typeof SECTORS)[number]
