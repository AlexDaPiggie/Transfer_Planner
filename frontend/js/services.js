import { startTypingHeadline, typingHeadlineMarkup } from "./typing_headline.js";

export function renderServiceHome(app) {
  app.innerHTML = `
    <section class="hero home-hero" aria-labelledby="home-title">
      <p class="eyebrow">De Anza Guide</p>
      ${typingHeadlineMarkup("Let's make College Easier")}
    </section>
    <section class="service-grid" aria-label="De Anza Guide services">
        <article class="card service-card planner-service"><span class="service-card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z"/><path d="M4 6h13M8 10h8m-8 4h6"/></svg></span><span class="service-eyebrow">Transfer Planner</span><p>Build a transfer plan with verified ASSIST courses.</p><a class="primary" href="?service=transfer">Plan your transfer <span aria-hidden="true">→</span></a></article>
        <article class="card service-card chat-service"><span class="service-card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.7 8.7 0 0 1-3.7-.8L4 20l1.2-3.7A7.1 7.1 0 0 1 4 12c0-4.1 3.6-7.5 8-7.5s8 3.1 8 7Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></svg></span><span class="service-eyebrow">De Anza Chatbot</span><p>Get answers about courses, deadlines, and campus services.</p><a class="primary" href="?service=chat">Ask De Anza <span aria-hidden="true">→</span></a></article>
    </section>`;
  const homeHeadline = app.querySelector(".typing-headline");
  homeHeadline.id = "home-title";
  startTypingHeadline(homeHeadline);
}

export function renderChatbot(app) {
  app.classList.add("chatbot-page");
  app.innerHTML = `<section class="chatbot-service" aria-label="De Anza Chatbot"><iframe class="chatbot-frame" title="De Anza Chatbot" src="/chatbot/?embed=1"></iframe></section>`;
}
