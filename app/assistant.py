"""Role-filtered retrieval with optional model selection of verifiable quotations."""
from collections import Counter
from difflib import get_close_matches
import math
import re

STOP = set("как какой какая какие где когда мне меня мой моя мои у в во на по и а с со для ли это о об что чем могу можно пожалуйста нужно из я про есть сколько кого кто если при чтобы подскажите подскажи расскажи сделать делать моем моём моего мне вашем вашей бы ли это же то или хочу хотим надо мне пожалуйста the a an how what when is are to of my do i здравствуйте привет".split())
SUFFIXES = ("иями", "ение", "ения", "ению", "ении", "ости", "ость", "или", "ила", "ило", "ена", "ено", "ены", "ать", "ить", "ять", "еть", "ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими", "иях", "ах", "ях", "ов", "ев", "ей", "ой", "ий", "ый", "ая", "яя", "ое", "ее", "ые", "ие", "ам", "ям", "ом", "ем", "ен", "а", "я", "ы", "и", "у", "ю", "е", "о", "ь")
REFUSAL = "В доступных вам документах нет надёжного ответа на этот вопрос. Обратитесь в HR. Я не могу подтверждать правила, которых нет в источниках."

SYNONYMS = {
    "заявок": "заявка",
    "заявление": "заявка",
    "заявления": "заявка",
    "заявлению": "заявка",
    "заявлением": "заявка",
    "заявлении": "заявка",
    "заявлений": "заявка",
    "взять": "оформить",
    "уйти": "оформить",
    "пойти": "оформить",
    "аннулировать": "отменить",
    "отозвать": "отменить",
    "видна": "увидеть",
    "видно": "увидеть",
    "видны": "доступны",
    "увижу": "увидеть",
    "почему": "причина",
    "пересдать": "тест",
    "пересдача": "тест",
    "обучение": "курс",
    "обучения": "курс",
    "обучению": "курс",
    "учеба": "курс",
    "зарегистрировать": "добавить",
    "завести": "добавить",
    "уведомлениях": "уведомления",
    "колокольчик": "уведомления",
    "проверить": "посмотреть",
    "посмотреть": "увидеть",
    "узнать": "посмотреть",
    "найти": "увидеть",
    "скоко": "сколько",
    "поменять": "изменить",
    "поменял": "изменить",
    "поменяется": "изменить",
    "исправить": "изменить",
    "сменить": "изменить",
    "бот": "помощник",
    "бота": "помощник",
    "боту": "помощник",
    "ботом": "помощник",
    "прочитать": "прочитанными",
    "завалил": "неверный",
    "провалил": "неверный",
}


def canonical_word(word):
    seen = set()
    while word in SYNONYMS and word not in seen:
        seen.add(word)
        word = SYNONYMS[word]
    return word


def edit_distance(s1, s2):
    if abs(len(s1) - len(s2)) > 1:
        return 2
    if s1 == s2:
        return 0
    if len(s1) == len(s2):
        return sum(c1 != c2 for c1, c2 in zip(s1, s2))
    short, long_ = (s1, s2) if len(s1) < len(s2) else (s2, s1)
    for i in range(len(long_)):
        if long_[:i] + long_[i+1:] == short:
            return 1
    return 2


def stem_word(word):
    if len(word) > 5 and word.endswith(("ся", "сь")):
        word = word[:-2]
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[:-len(suffix)]
            break
    return word


def tokens(value):
    result = []
    for word in re.findall(r"[a-zа-я0-9]+", value.lower().replace("ё", "е")):
        if word in STOP or len(word) < 2:
            continue
        mapped = canonical_word(word)
        result.append(stem_word(mapped))
    return result


def status():
    from .model import configuration
    config = configuration()
    provider, model, enabled = config['provider'], config['model'], config['enabled']
    return {"mode": "grounded_llm" if enabled else "extractive", "model_enabled": enabled,
            "provider": provider, "model": model,
            "note": f"Настроен режим модели ({provider}: {model}) с проверкой цитат. Доступность проверяется при запросе." if enabled else "Локальный поиск по документам. Внешняя модель не подключена."}


def rank(question, articles):
    raw_query = [w for w in re.findall(r"[a-zа-я0-9]+", question.lower().replace("ё", "е")) if w not in STOP and len(w) >= 2]
    if not raw_query:
        return []
    # An infinitive asks how to perform an action. Do not mistake a passive
    # status (e.g. "отклонена") for instructions ("отклонить").

    corpus_raw = set()
    for a in articles:
        for w in re.findall(r"[a-zа-я0-9]+", (a["title"] + " " + a.get("summary", "") + " " + a["content"]).lower().replace("ё", "е")):
            if w not in STOP and len(w) >= 2:
                corpus_raw.add(w)

    normalized_words = []
    for word in raw_query:
        mapped = canonical_word(word)
        if mapped in corpus_raw or word in corpus_raw:
            normalized_words.append(mapped)
            continue
        if len(word) >= 4:
            candidates = [v for v in corpus_raw if edit_distance(word, v) <= 1]
            if len(candidates) == 1:
                mapped = canonical_word(candidates[0])
                normalized_words.append(mapped)
                continue
            matches = get_close_matches(word, sorted(corpus_raw), n=2, cutoff=0.86)
            if len(matches) == 1:
                mapped = canonical_word(matches[0])
                normalized_words.append(mapped)
                continue
        normalized_words.append(mapped)

    actions = {word for word in normalized_words if word.endswith(('ить', 'ать', 'ять', 'еть'))}
    query = set(stem_word(w) for w in normalized_words)
    if not query:
        return []

    corpus = [(a, Counter(tokens(a["title"] + " " + a.get("summary", "") + " " + a["content"]))) for a in articles]
    vocabulary = set().union(*(set(counts) for _, counts in corpus)) if corpus else set()

    normalized = set()
    for word in query:
        if word not in vocabulary and len(word) >= 5:
            matches = get_close_matches(word, sorted(vocabulary), n=2, cutoff=0.86)
            if len(matches) == 1:
                word = matches[0]
        normalized.add(word)

    average = sum(sum(counts.values()) for _, counts in corpus) / max(len(corpus), 1)
    frequency = {word: sum(word in counts for _, counts in corpus) for word in normalized}

    all_passages_tokens = []
    for a, _ in corpus:
        ps = [a["title"] + " " + a.get("summary", "")] + re.split(r"[.!?\n]+", a["content"])
        for p in ps:
            pt = tokens(p)
            if pt:
                all_passages_tokens.append(len(pt))
    avg_p_len = sum(all_passages_tokens) / max(len(all_passages_tokens), 1)

    ranked = []
    for article, counts in corpus:
        covered = normalized & counts.keys()
        if not covered:
            continue
        score = 0.0
        for word in covered:
            inverse = math.log(1 + (len(corpus) - frequency[word] + 0.5) / (frequency[word] + 0.5))
            tf = counts[word]
            score += inverse * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * sum(counts.values()) / max(average, 1)))

        passages = [article["title"] + " " + article.get("summary", "")] + re.split(r"[.!?\n]+", article["content"])
        matching_passages = [p for p in passages if normalized <= set(tokens(p))]
        passage_match = bool(matching_passages)
        article_words = {canonical_word(word) for word in re.findall(
            r'[a-zа-я0-9]+', (article['title'] + ' ' + article.get('summary', '') + ' ' + article['content']).lower().replace('ё', 'е'))}
        action_match = actions <= article_words

        best_p_score = 0.0
        for p in matching_passages:
            p_toks = tokens(p)
            p_counts = Counter(p_toks)
            p_score = 0.0
            for word in normalized:
                inverse = math.log(1 + (len(corpus) - frequency[word] + 0.5) / (frequency[word] + 0.5))
                p_tf = p_counts[word]
                p_score += inverse * p_tf * 2.2 / (p_tf + 1.2 * (0.25 + 0.75 * len(p_toks) / max(avg_p_len, 1)))
            if p_score > best_p_score:
                best_p_score = p_score

        final_score = score + best_p_score
        ranked.append({"article": article, "coverage": len(covered)/len(normalized), "score": final_score, "passage_match": passage_match, "action_match": action_match})
    return sorted(ranked, key=lambda r: (r["passage_match"], r["coverage"], r["score"]), reverse=True)


def answer(question, articles, own_profile):
    result = {"found": False, "mode": "extractive", "sources": [], "answer": REFUSAL, "evidence": []}
    # Pure greetings/help are interface conversation, never a sourced HR claim
    # or evidence of a live provider call. Mixed HR questions use normal retrieval.
    social = ' '.join(re.findall(r'[a-zа-яәіңғүұқөһ0-9]+', question.casefold()))
    greetings = {'привет', 'првиет', 'приветик', 'здравствуй', 'здравствуйте', 'добрый день',
                 'доброе утро', 'добрый вечер', 'сәлем', 'салем', 'hello', 'hi', 'привет яна', 'привет jana'}
    help_phrases = {'что ты умеешь', 'что ты можешь', 'кто ты', 'как дела', 'помощь', 'help'}
    if social in greetings | help_phrases:
        return {**result, 'mode': 'conversation', 'answer':
                'Привет! Я AI Jana, ваш HR-помощник. Помогу найти ответ в доступных документах, '
                'разобраться с заявкой на отпуск и обучением. '
                'Попробуйте: «Как подать заявку на отпуск?» или «Какой у меня остаток отпуска?».'}
    if social in {'спасибо', 'благодарю', 'спасибо большое', 'рахмет', 'thanks', 'thank you'}:
        return {**result, 'mode': 'conversation', 'answer': 'Пожалуйста! Если появится вопрос об отпуске или обучении — напишите.'}
    words = set(tokens(question))
    # Exact record lookup is limited to the current session's profile, never the team.
    is_balance_query = (any(word.startswith(("остат", "остал", "доступн")) for word in words) or "скольк" in words) and any(word.startswith("отпуск") for word in words)
    if is_balance_query:
        allowed = {"остаток", "остат", "осталось", "остал", "отпуск", "день", "дней", "доступно", "доступн", "скольк", "дн"}
        if words <= allowed and (any(w.startswith(("остат", "остал", "доступн")) for w in words) or "скольк" in words):
            result.update(found=True, answer=f"В вашем профиле доступно {own_profile['vacation_balance']} дней отпуска. Источник: ваш текущий профиль.",
                          sources=[{"id": own_profile["id"], "title": "Мой профиль", "url": "/api/profile"}])
            return result
        if re.search(r"\b(меня|мой|моего|мои|чужой|другого|коллеги)\b", question.lower()):
            return result
    ranked = [item for item in rank(question, articles) if item['action_match']]
    if not ranked:
        return result
    configuration = status()
    notice = None
    if configuration["model_enabled"]:
        from .model import select_quotes, ProviderUnavailable
        try:
            selection = select_quotes(question, [r["article"] for r in ranked[:4]])
            if not selection:
                return {**result, "mode": "grounded_llm"}
            seen, sources = set(), []
            for item in selection:
                if item["source_id"] not in seen:
                    article = next(a for a in articles if a["id"] == item["source_id"])
                    sources.append({"id": article["id"], "title": article["title"], "url": f"/api/knowledge/{article['id']}"})
                    seen.add(article["id"])
            return {"found": True, "mode": "grounded_llm", "sources": sources,
                    "answer": "\n\n".join(item["quote"] for item in selection), "evidence": selection}
        except ProviderUnavailable:
            notice = "Модель недоступна или не подтвердила цитаты. Использован локальный поиск."
    # No fuzzy confidence is represented as probability; full term coverage is required.
    exact = [entry for entry in ranked if entry["coverage"] == 1 and entry["passage_match"]]
    if exact:
        article = exact[0]["article"]
        result.update(found=True, answer=article["content"], sources=[{"id": article["id"], "title": article["title"], "url": f"/api/knowledge/{article['id']}"}],
                      evidence=[{"source_id": article["id"], "quote": article["content"]}])
    if notice:
        result["notice"] = notice
    return result

