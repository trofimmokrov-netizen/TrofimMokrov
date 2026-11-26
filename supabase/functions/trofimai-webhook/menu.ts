const site = "https://trofimmokrov-netizen.github.io/TrofimMokrov";
export function startMenu(update: any) {
  const m = update?.message;
  if (m?.chat?.type !== "private" || !Number.isSafeInteger(m.chat.id) || m.from?.id !== m.chat.id || typeof m.text !== "string") return null;
  const command = m.text.trim();
  if (!/^\/(start|menu)(?:@TrofimAI_bot)?$/i.test(command)) return null;
  return {chat_id:m.chat.id,text:"Здравствуйте! Я помощник Трофима Мокрова. Помогу выбрать услугу и оформить заявку.",reply_markup:{resize_keyboard:true,keyboard:[[{text:"Открыть приложение",web_app:{url:site+"/miniapp/"}}],[{text:"Услуги и цены"},{text:"Портфолио"}],[{text:"Оставить заявку"},{text:"Обо мне"}],[{text:"Помощник"},{text:"Контакты"}]]}};
}
