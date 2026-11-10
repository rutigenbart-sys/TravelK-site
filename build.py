#!/usr/bin/env python3
"""Travel&K site generator.

Reads data/*.json (edited from /admin/) + templates/ and writes the finished static
site into _site/. Runs in GitHub Actions on every push to main. Standard library only.
"""
import os, re, json, html, shutil, sys, glob, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, os.environ.get('BUILD_OUT', '_site'))
SITE = 'https://travelk.shop'
B = '@@B@@'

# ---------------------------------------------------------------- helpers
def jl(path):
    with open(os.path.join(ROOT, path), encoding='utf8') as f:
        return json.load(f)

def e(s):            # escape for text and attributes (matches the original generator)
    return html.escape(str(s), quote=True)

def money(n):
    return '{:,}'.format(int(n)).replace(',', ' ')

def ps(n):           # price string
    return money(n) + ' ฿'

def pe(slug, key, v, pre=''):
    return '%s<span class="pe" data-pk="%s:%s" data-v="%d">%s</span>' % (pre, slug, key, v, ps(v))

def jdump(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))

SHELL = jl('templates/shell.json')

def _rd(name):
    with open(os.path.join(ROOT, 'templates', name), encoding='utf8') as f:
        return f.read().strip()

# Единый источник прелоадера: templates/preloader.{css,head.js,html}
PRE_HEAD = ('<link rel="preload" href="@@B@@assets/fonts/pf-lat.woff2" as="font" type="font/woff2" crossorigin>'
            '<style>' + _rd('preloader.css') + '</style><script>' + _rd('preloader.head.js') + '</script>')
PRE_BODY = _rd('preloader.html')

def inject_pre(s):
    return s.replace('<!--PRE_HEAD-->', PRE_HEAD).replace('<!--PRE_BODY-->', PRE_BODY)

# ---------------------------------------------------------------- data
def load_data():
    d = {}
    d['site'] = jl('data/site.json')
    d['cats'] = jl('data/categories.json')
    tours = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'data/tours/*.json'))):
        t = json.load(open(p, encoding='utf8'))
        t['prices'] = [p for p in t.get('prices', []) if (p.get('v') or 0) > 0]
        if not t['prices'] or (t.get('published', True) and not t.get('title')):
            print('WARN: %s has no positive price -> treated as hidden' % t['slug'], file=sys.stderr)
            t['published'] = False
            t['prices'] = [{'k': 'a', 'l': '', 'v': 0}]
        tours[t['slug']] = t
    d['tours'] = tours
    d['vizy'] = jl('data/vizy.json'); d['partners'] = jl('data/partners.json')
    d['promos'] = jl('data/promos.json'); d['transfer'] = jl('data/transfer.json')
    blog = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'data/blog/*.json'))):
        b = json.load(open(p, encoding='utf8'))
        blog[b['slug']] = b
    d['blog'] = blog
    d['home'] = jl('data/home.json')
    return d

# ---------------------------------------------------------------- shell
def nav_marks(active):
    return {n: ('on' if n == active else '') for n in ('ekskursii', 'transfer', 'vizy', 'partnery', 'akcii', 'blog', 'kontakty')}

def head(depth_base, title, desc, path, og_image=None, ld=(), noindex=False, old_og=False, extra_preload='', canon=True):
    url = SITE + '/' + path
    h = SHELL['head_start']
    h += '<title>%s</title><meta name="description" content="%s">' % (e(title), e(desc))
    if canon:
        h += '<link rel="canonical" href="%s">' % url
    if noindex:
        h += '<meta name="robots" content="noindex">'
    h += '\n<meta property="og:type" content="website"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s">' % (e(title), e(desc), url)
    if old_og:
        h += '<meta property="og:image" content="%s/%s">' % (SITE, og_image) + '<meta property="og:locale" content="ru_RU">'
    else:
        h += ('<meta property="og:image" content="%s/img/og-share.jpg"><meta property="og:image:type" content="image/jpeg">'
              '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
              '<meta property="og:image:alt" content="Travel&amp;K — экскурсии, трансферы и визы в Таиланде">'
              '<meta property="og:site_name" content="Travel&amp;K"><meta name="twitter:card" content="summary_large_image">'
              '<meta name="twitter:image" content="%s/img/og-share.jpg"><meta property="og:locale" content="ru_RU">') % (SITE, SITE)
    h += '<meta name="theme-color" content="#07111c">\n'
    mid = SHELL['head_mid']
    if extra_preload:
        mid = mid.replace('<link rel="apple-touch-icon"', extra_preload + '<link rel="apple-touch-icon"', 1) if False else mid
    h += mid
    for l in ld:
        h += '<script type="application/ld+json">%s</script>' % l
    h += SHELL['head_end']
    return h

def breadcrumb_ld(items):
    out = []
    for i, (name, url) in enumerate(items):
        out.append({'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': url})
    return jdump({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': out})

def page(base, active, head_html, main, qr=False, home=False):
    top = SHELL['body_top']
    for n, v in nav_marks(active).items():
        top = top.replace('{{on:%s}}' % n, v)
    bottom = SHELL['body_bottom']
    if qr:
        bottom = bottom.replace('<script src="@@B@@assets/app.js', '<script src="@@B@@assets/qr.js"></script><script src="@@B@@assets/app.js', 1)
    out = inject_pre(head_html + '\n' + top + main + bottom)
    return out.replace(B, base)

# ---------------------------------------------------------------- tours
def photo_src(ph):
    return ph['s'] if isinstance(ph, dict) else ph

def cat_title(cats, key):
    for c in cats:
        if c['key'] == key:
            return c['title']
    return key

def tour_cover(t):
    return photo_src(t['photos'][0]) if t['photos'] else 'img/og-share.jpg'

def first_price(t):
    return t['prices'][0]['v'] if t['prices'] else 0

def tour_days_time(t):
    if 'days' in t:
        return [x for x in (t.get('days', ''), t.get('time', '')) if x and x not in ('Уточняется', 'По запросу')]
    return t.get('card_meta', [])

def card(t, cats, base):
    ct = cat_title(cats, t['cat'])
    meta = ''.join('<span>%s</span>' % e(x) for x in tour_days_time(t))
    return ('<a class="card" href="%sekskursii/%s/" data-t="%s" data-c="%s" data-p="%d"><div class="im"><img src="%s%s" alt="%s" width="720" height="%d" loading=lazy decoding=async>'
            '<span class="badge">%s</span></div><div class="bd"><h3>%s</h3><div class="meta">%s</div><div class="ft"><div class="price"><small>%s</small>%s</div></div></div></a>') % (
        base, t['slug'], e((t['title'] + ' ' + ct).lower()), t['cat'], first_price(t), base, tour_cover(t), e(t['title']), t.get('card_h', 540), e(t.get('card_badge', ct)), e(t['title']), meta,
        e(t.get('price_label', 'взрослый')), pe(t['slug'], t.get('card_pk', t['prices'][0]['k']), t['prices'][0]['v']))

def price_row(t, cats, base):
    ct = cat_title(cats, t['cat'])
    adult = pe(t['slug'], t.get('card_pk', t['prices'][0]['k']), t['prices'][0]['v'])
    child = pe(t['slug'], t['prices'][1]['k'], t['prices'][1]['v']) if len(t['prices']) > 1 else '—'
    ov = t.get('row', {})
    rd = ov.get('days', t.get('days', '')); rt = ov.get('time', t.get('time', ''))
    rd = '' if rd == 'Уточняется' else rd; rt = '' if rt == 'Уточняется' else rt
    if ov.get('child') is False: child = '—'
    return ('<tr data-t="%s" data-c="%s" data-p="%d"><td class="n"><a href="%sekskursii/%s/">%s</a><br><small style="color:var(--muted)">%s</small></td>'
            '<td>%s</td><td>%s</td><td class="p">%s</td><td class="p">%s</td><td><button class="btn sm" data-open="%s">Заявка</button></td></tr>') % (
        e((t['title'] + ' ' + ct).lower()), t['cat'], first_price(t), base, t['slug'], e(t['title']), e(ct),
        e(rd), e(rt), adult, child, e(t['title']))

def prose_html(t):
    out = ''
    for b in t['body']:
        k = b['t']
        if k in ('h2', 'h3'):
            out += '<%s>%s</%s>' % (k, e(b['x']), k)
        elif k == 'p':
            out += '<p>%s</p>' % e(b['x'])
        elif k == 'note':
            out += '<p style="%s">%s</p>' % (b.get('style', 'color:var(--muted);font-size:.85rem'), e(b['x']))
        elif k == 'ul':
            out += '<ul>%s</ul>' % ''.join('<li>%s</li>' % e(x) for x in b['x'])
        else:
            out += expand_raw(b['x'], t)
    return out

def expand_raw(x, t):
    def rep(m):
        for pr in t['prices']:
            if pr['k'] == m.group(1):
                return pe(t['slug'], pr['k'], pr['v'])
        return ''
    return re.sub(r'\{\{pe:([a-z0-9_-]+)\}\}', rep, x)

def tour_facts(t):
    if 'facts' in t:
        return t['facts']
    return [{'l': 'Дни выезда', 'v': t.get('days', '')}, {'l': 'Время', 'v': t.get('time', '')},
            {'l': 'Возраст / рост ребёнка', 'v': t.get('age', 'Уточняется')}, {'l': 'Формат', 'v': t.get('format', '')}]

def tour_cc(t):
    if 'cc' in t:
        return t['cc']
    return [x for x in (t.get('days', ''), t.get('time', ''), t.get('format', '')) if x and x != 'Уточняется']

def desc_for(t):
    if t.get('meta'):
        return t['meta']
    src = next((b['x'] for b in t['body'] if b['t'] == 'p'), '') or t.get('lead', '')
    return '%s: %s… Цена от %s. Заявка за 1 минуту.' % (t['title'], src[:150], ps(first_price(t)))

def tour_page(t, D):
    cats = D['cats']; slug = t['slug']
    B2 = B
    ct = cat_title(cats, t['cat'])
    title_h = e(t['title'])
    # gallery
    figs = ''
    for i, ph in enumerate(t['photos']):
        s = photo_src(ph)
        alt = ph.get('alt') if isinstance(ph, dict) and 'alt' in ph else '%s — фото %d' % (t['title'], i + 1)
        w = ph.get('w', 1000) if isinstance(ph, dict) else 1000
        h_ = ph.get('h', 750) if isinstance(ph, dict) else 750
        attrs = 'fetchpriority=high' if i == 0 else 'loading=lazy'
        cap = ''
        if i == 0:
            cp = ''
            if t.get('cp', True) and t['prices']:
                cp = '<span class="cp">%s</span>' % ps(first_price(t))
            cap = '<figcaption class="cap"><span class="ck">%s</span><div class="cc">%s</div>%s</figcaption>' % (
                e(t['kicker']), ''.join('<span>%s</span>' % e(x) for x in tour_cc(t)), cp)
        figs += '<figure><img src="%s%s" alt="%s" width=%d height=%d %s decoding=async>%s</figure>' % (B2, s, e(alt), w, h_, attrs, cap)
    gal = '<div class="gal%s">%s</div>' % (' one' if len(t['photos']) == 1 else '', figs)
    facts = '<div class="facts">%s</div>' % ''.join('<div class="fact"><small>%s</small><b>%s</b></div>' % (e(f['l']), e(f['v'])) for f in tour_facts(t))
    after = expand_raw(t.get('after_facts', ''), t)
    prose = '<div class="prose">%s</div>' % prose_html(t)
    lead = '<p class="lead">%s</p>' % e(t['lead']) if t.get('lead') else ''
    # aside
    prs = ''.join('<div><small>%s</small><b>%s</b></div>' % (e(p['l']), pe(slug, p['k'], p['v'], p.get('pre', ''))) for p in t['prices'])
    note = '<div class="note" style="margin-bottom:14px">%s</div>' % e(t['book_note']) if t.get('book_note') else ''
    if t.get('book_select'):
        tourfield = '<label>Пакет<select name="tour">%s</select></label>' % ''.join('<option>%s</option>' % e(o) for o in t['book_select'])
    else:
        tourfield = '<input type="hidden" name="tour" value="%s">' % title_h
    btn = e(t.get('book_btn', 'Заказать экскурсию'))
    aside = ('<aside class="book panel"><h3 style="margin-bottom:14px">Стоимость</h3><div class="pr">%s</div>%s<form class="form" novalidate onsubmit="return false"><div class="fields">\n'
             '<div class="row"><label>Имя<input name="name" required autocomplete="name" placeholder="Как к вам обращаться"></label><label>Telegram / WhatsApp / телефон<input name="contact" required autocomplete="tel" placeholder="@username или +7…"></label></div>\n'
             '%s<label>Желаемая дата<input name="date" type="date"></label><div class="row"><label>Взрослых<input name="adults" type="number" min="1" max="30" value="2" inputmode="numeric"></label><label>Детей<input name="kids" type="number" min="0" max="20" value="0" inputmode="numeric"></label></div><label>Отель / район<input name="hotel" placeholder="Например: Паттайя, Джомтьен"></label>\n'
             '<label>Комментарий<textarea name="comment" placeholder="Пожелания, вопросы"></textarea></label>\n'
             '<input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">\n'
             '<button class="btn wide" type="submit">%s</button>\n'
             '<small>Нажимая кнопку, вы соглашаетесь с <a href="%spolitika/" style="text-decoration:underline">политикой обработки данных</a>. Ответим в течение часа в мессенджере.</small></div>\n'
             '<div class="ok">Спасибо! Заявка отправлена — мы свяжемся с вами в Telegram или WhatsApp.</div></form></aside>') % (prs, note, tourfield, btn, B2)
    rel = ''
    if t.get('related') is not None:
        relt = [D['tours'][s] for s in related_for(t, D)]
        if relt:
            rel = ('\n<div class="sec tight"><div class="sec-h"><h2>Похожие экскурсии</h2><a class="btn ghost sm" href="%sekskursii/#%s">Все в категории</a></div><div class="cards">%s</div></div>'
                   % (B2, t['cat'], ''.join(card(x, cats, B2) for x in relt)))
    main = ('<main><div class="wrap"><div class="ph-head" style="padding-bottom:10px"><div class="crumbs"><a href="%s">Главная</a> <span>/</span> <a href="%sekskursii/">Экскурсии</a> <span>/</span> <span>%s</span></div>'
            '<span class="eyebrow">%s</span><h1 style="font-size:clamp(1.8rem,4vw,2.8rem)">%s</h1>%s</div>\n'
            '<div class="tour"><div>%s%s%s%s</div>\n%s</div>%s</div></main>') % (B2, B2, title_h, e(t['kicker']), title_h, lead, gal, facts, after, prose, aside, rel)
    # head
    desc = desc_for(t)
    url = 'ekskursii/%s/' % slug
    first_p = next((b['x'] for b in t['body'] if b['t'] == 'p'), '') or t.get('lead', '')
    ld = [breadcrumb_ld([('Главная', SITE + '/'), ('Экскурсии', SITE + '/ekskursii/'), (t['title'], SITE + '/')]),
          jdump({'@context': 'https://schema.org', '@type': 'TouristTrip', 'name': t['title'], 'description': t.get('ld_desc', first_p[:300]), 'inLanguage': 'ru',
                 'provider': {'@type': 'TravelAgency', 'name': 'Travel&K', 'telephone': '+66648657933', 'url': SITE + '/'},
                 'offers': {'@type': 'Offer', 'price': first_price(t), 'priceCurrency': 'THB', 'availability': 'https://schema.org/InStock', 'url': SITE + '/' + url}})]
    hh = head(None, '%s — цена и программа | Travel&K' % t['title'], desc, url, og_image=tour_cover(t), ld=ld, old_og=not t.get('og_new'))
    return url, page('../../', 'ekskursii', hh, main)

def related_for(t, D):
    """Explicit list from data, with hidden/removed tours filtered out and topped up from the same category."""
    pub = {s: x for s, x in D['tours'].items() if x.get('published', True)}
    rel = [s for s in t.get('related', []) if s in pub and s != t['slug']]
    if len(rel) < 3 and t.get('related'):
        pool = sorted((x for x in pub.values() if x['cat'] == t['cat'] and x['slug'] != t['slug'] and x['slug'] not in rel), key=lambda x: x['order'])
        rel += [x['slug'] for x in pool][:3 - len(rel)]
    return rel[:3]

# ---------------------------------------------------------------- catalog & directions
def cat_list(D):
    return D['cats']

def ordered_tours(D):
    return sorted((t for t in D['tours'].values() if t.get('published', True)), key=lambda t: t['order'])

def catalog_block(D, tours, base, active_cat, link_pills):
    cats = D['cats']
    if link_pills:
        pills = ''.join('<a class="pill%s" href="%snapravleniya/%s/">%s</a>' % (' on' if c['key'] == active_cat else '', base, c['key'], e(c['title'])) for c in cats)
    else:
        pills = '<button class="pill on" data-c="all">Все</button>' + ''.join('<button class="pill" data-c="%s">%s</button>' % (c['key'], e(c['title'])) for c in cats)
    tools = ('<section id="catalog"><div class="tools"><div class="wrap"><div class="row"><div class="pills">%s</div><input type="search" id="q" placeholder="Поиск экскурсии" aria-label="Поиск">'
             '<select id="sort" aria-label="Сортировка"><option value="def">По умолчанию</option><option value="asc">Сначала дешевле</option><option value="desc">Сначала дороже</option></select>'
             '<div class="seg"><button class="on" data-v="cards">Карточки</button><button data-v="table">Прайс</button></div></div></div></div>\n') % pills
    body = ('<div class="wrap"><p style="color:var(--muted);margin-bottom:16px">Найдено: <b id="cnt">%d</b>. Цены в батах (฿) за человека; детские цены — для указанного возраста.</p>'
            '<div class="cards">%s</div><div class="tbl scroll"><table><thead><tr><th>Экскурсия</th><th>Дни</th><th>Время</th><th>Взрослый</th><th>Ребёнок</th><th></th></tr></thead><tbody>%s</tbody></table></div>'
            '<div class="empty">Ничего не найдено — попробуйте другой запрос или напишите нам, подберём вручную.</div></div></section>') % (
        len(tours), ''.join(card(t, cats, base) for t in tours), ''.join(price_row(t, cats, base) for t in tours))
    return tools + body

def catalog_page(D):
    tours = ordered_tours(D)
    main = ('<main><div class="wrap ph-head"><div class="crumbs"><a href="%s">Главная</a> <span>/</span> <span>Экскурсии</span></div><h1>Экскурсии по Таиланду</h1>'
            '<p class="lead">Весь каталог Travel&K: %d программ с ценами в батах. Фильтруйте по направлению, переключайтесь на прайс-таблицу и оставляйте заявку в один клик.</p></div>') % (B, len(tours))
    main += catalog_block(D, tours, B, None, False) + '</main>'
    ld = [breadcrumb_ld([('Главная', SITE + '/'), ('Экскурсии', SITE + '/')])]
    hh = head(None, 'Экскурсии по Таиланду — каталог и цены | Travel&K',
              'Каталог экскурсий по Таиланду с ценами: острова, Бангкок, Аюттайя, Река Квай, север, зоопарки, шоу. Гиды на русском языке.', 'ekskursii/', ld=ld)
    return 'ekskursii/', page('../', 'ekskursii', hh, main)

def direction_page(D, c):
    tours = [t for t in ordered_tours(D) if t['cat'] == c['key']]
    if not tours:
        return None
    mn = min(first_price(t) for t in tours)
    lead = '%s В категории %d программ, цены от %s.' % (c['lead'], len(tours), ps(mn))
    main = ('<main><div class="wrap ph-head"><div class="crumbs"><a href="%s">Главная</a> <span>/</span> <a href="%sekskursii/">Экскурсии</a> <span>/</span> <span>%s</span></div>'
            '<h1>%s</h1><p class="lead">%s</p></div>' ) % (B, B, e(c['title']), e(c['title']), e(lead))
    main += catalog_block(D, tours, B, c['key'], True) + '</main>'
    url = 'napravleniya/%s/' % c['key']
    ld = [breadcrumb_ld([('Главная', SITE + '/'), ('Экскурсии', SITE + '/ekskursii/'), (c['title'], SITE + '/')])]
    hh = head(None, c.get('meta_title') or '%s в Таиланде — цены и программы | Travel&K' % c['title'],
              '%s Цены от %s.' % (c['desc'], ps(mn)), url, ld=ld)
    return url, page('../../', 'ekskursii', hh, main)


# ---------------------------------------------------------------- simple list pages
def tpl(name):
    with open(os.path.join(ROOT, 'templates', name), encoding='utf8') as f:
        return f.read()

PAGES_HEAD = jl('templates/pages_head.json')

def pub(items):
    return [x for x in items if x.get('published', True)]

def static_head(key, path, noindex=False):
    ph = PAGES_HEAD[key]
    return head(None, ph['title'], ph['desc'], path, ld=ph['ld'], noindex=noindex)

def vizy_page(D):
    V = D['vizy']
    svc = ''.join(('<div class="tile"><span class="eyebrow" style="margin:0">%s</span><h3>%s</h3><p>%s</p><div class="meta" style="display:flex;gap:12px;color:var(--muted);font-size:.88rem"><span>%s</span><span>%s</span></div>'
                   '<div class="price" style="margin-top:auto"><small>от</small>%s</div><button class="btn" data-open="Виза: %s">Заказать</button></div>') % (
        e(s['eyebrow']), e(s['title']), e(s['text']), e(s['days']), e(s['time']), pe('visa', s['id'], s['price']).replace('data-pk="visa:%s"' % s['id'], 'data-pk="visa:%s"' % s['id']), e(s['title'])) for s in pub(V['services']))
    what = ''.join('<div class="tile"><div class="ic">%s</div><h3>%s</h3><p>%s</p></div>' % (e(w['ic']), e(w['title']), e(w['text'])) for w in pub(V['what']))
    main = tpl('vizy.html').replace('{{services}}', svc).replace('{{what}}', what)
    return 'vizy/', page('../', 'vizy', static_head('vizy', 'vizy/'), main)

def partnery_page(D):
    P = D['partners']
    tiles = ''.join(('<div class="tile"><div class="ic">%s</div><h3>%s</h3><p>%s</p><p style="font-weight:700;color:var(--brand-d)">%s</p>'
                     '<button class="btn ghost sm" data-open="Партнёры: %s">Узнать условия</button></div>') % (e(t['ic']), e(t['title']), e(t['text']), e(t['promo']), e(t['title'])) for t in pub(P['tiles']))
    shops = ''.join(('<div class="route"><div><h3>%s</h3><p>%s</p></div><div class="pr"><b style="font-size:1rem">%s</b>'
                     '<span style="color:var(--muted);font-size:.8rem">%s</span></div></div>') % (e(s['title']), e(s['text']), e(s['price']), e(s['hours'])) for s in pub(P['shops']))
    main = tpl('partnery.html').replace('{{tiles}}', tiles).replace('{{shops}}', shops)
    return 'partnery/', page('../', 'partnery', static_head('partnery', 'partnery/'), main)

def tour_cards(D, slugs, base):
    out = ''
    for s in slugs:
        t = D['tours'].get(s)
        if t and t.get('published', True):
            out += card(t, D['cats'], base)
    return out

def akcii_page(D):
    A = D['promos']
    tiles = ''.join('<div class="tile%s"><div class="ic">%s</div><h3>%s</h3><p>%s</p><a class="btn%s sm" href="%s">%s</a></div>' % (
        ' dark' if t.get('dark') else '', e(t['ic']), e(t['title']), e(t['text']), '' if t.get('dark') else ' ghost', t['href'], e(t['btn'])) for t in pub(A['tiles']))
    secs = '\n'.join('<div class="sec tight"><div class="sec-h"><div><span class="eyebrow">%s</span><h2>%s</h2></div></div><div class="cards">%s</div></div>' % (
        e(s['eyebrow']), e(s['title']), tour_cards(D, s['tours'], B)) for s in A['sections'])
    main = tpl('akcii.html').replace('{{tiles}}', tiles).replace('{{sections}}', secs)
    return 'akcii/', page('../', 'akcii', static_head('akcii', 'akcii/'), main)

def transfer_page(D):
    T = D['transfer']
    routes = ''.join(('<div class="route" data-k="%s" data-p="%s"><div><h3>%s</h3><p>%s</p></div><div class="pr"><b class="pv">%s</b><span style="color:var(--muted);font-size:.8rem">за машину</span><br>'
                      '<button class="btn sm" data-open="Трансфер: %s">Заказать</button></div></div>') % (
        r['k'], ','.join(str(x) for x in r['p']), e(r['title']), e(r['text']), ps(r['p'][0]), e(r['title'])) for r in pub(T['routes']))
    bus = ''.join(('<tr><td class="n">%s<br><small style="color:var(--muted)">%s</small></td><td>%s</td><td class="p">%s</td><td class="p">%s</td>'
                   '<td><button class="btn sm" data-open="Минибас: %s">Заказать</button></td></tr>') % (
        e(r['title']), e(r['text']), e(r['time']), pe('bus:' + r['k'], 'a', r['a']), pe('bus:' + r['k'], 'c', r['c']), e(r['title'])) for r in pub(T['bus']))
    main = tpl('transfer.html').replace('{{routes}}', routes).replace('{{bus}}', bus).replace('{{tickets}}', tour_cards(D, T['tickets'], B))
    return 'transfer/', page('../', 'transfer', static_head('transfer', 'transfer/'), main)

def plain_page(key, path, active, noindex=False, qr=False):
    return path, page('../', active, static_head(key, path, noindex), tpl(key + '.html'), qr=qr)


# ---------------------------------------------------------------- blog
def art_svg(p):
    c1, c2 = p['art']
    return ('<svg viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice" role="img" aria-label="%s"><defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="%s" stop-opacity=".85"/><stop offset=".55" stop-color="#FFE9D2"/><stop offset="1" stop-color="%s" stop-opacity=".25"/></linearGradient></defs>'
            '<rect width="1200" height="600" fill="url(#s)"/><circle cx="880" cy="230" r="86" fill="#fff" opacity=".85"/>'
            '<path d="M0 420 Q160 330 320 400 T640 380 T960 410 T1200 360 V600 H0Z" fill="%s" opacity=".55"/>'
            '<path d="M0 470 Q200 410 400 460 T800 450 T1200 440 V600 H0Z" fill="%s" opacity=".8"/>'
            '<path d="M0 530 Q300 490 600 530 T1200 520 V600 H0Z" fill="%s"/></svg>') % (e(p['city']), c1, c2, c2, c2, c2)

def ordered_blog(D):
    return sorted([b for b in D['blog'].values() if b.get('published', True)], key=lambda b: b.get('order', 0))

def blog_card(p, base):
    im = ('<img src="%s%s" alt="%s" width="720" height="540" loading=lazy decoding=async>' % (base, p['img'], e(p['city']))) if p.get('img') else art_svg(p)
    d = p.get('card_desc') or (p['desc'][:110] + '…')
    return ('<a class="card" href="%sblog/%s/"><div class="im">%s<span class="badge">%s</span></div><div class="bd"><h3>%s</h3><div class="meta"><span>%s</span></div></div></a>'
            % (base, p['slug'], im, e(p['city']), e(p['title']), e(d)))

def blog_index_page(D):
    ph = PAGES_HEAD['blog']
    items = ordered_blog(D)
    main = ('<main><div class="wrap ph-head"><div class="crumbs"><a href="@@B@@">Главная</a> <span>/</span> <span>Блог</span></div><h1>Блог о городах Таиланда</h1>'
            '<p class="lead">Практичные гиды по популярным городам и островам: что посмотреть, когда ехать, как добраться и какие экскурсии выбрать.</p></div>'
            '<div class="wrap"><div class="cards">' + ''.join(blog_card(p, '@@B@@') for p in items) + '</div></div></main>')
    hd = head(None, ph['title'], ph['desc'], 'blog/', ld=ph['ld'])
    return 'blog/', page('../', 'blog', hd, main)

def blog_post_page(D, p):
    items = ordered_blog(D)
    url = 'blog/%s/' % p['slug']
    body = ''
    for b in p['body']:
        if b['t'] == 'ul':
            body += '<ul>' + ''.join('<li>%s</li>' % x for x in b['x']) + '</ul>'
        else:
            body += '<%s>%s</%s>' % (b['t'], b['x'], b['t'])
    hero = ('<img src="@@B@@%s" alt="%s" width="1000" height="500">' % (p['img'], e(p['title']))) if p.get('img') else art_svg(p)
    others = ''.join('<a class="pill" href="@@B@@blog/%s/">%s</a>' % (o['slug'], e(o['city'])) for o in items if o['slug'] != p['slug'])
    faq = ''.join('<details><summary>%s</summary><p>%s</p></details>' % (e(f['q']), e(f['a'])) for f in p['faq'])
    main = ('<main><div class="wrap"><article class="post"><div class="ph-head" style="padding-bottom:0"><div class="crumbs"><a href="@@B@@">Главная</a> <span>/</span> <a href="@@B@@blog/">Блог</a> <span>/</span> <span>%s</span></div>'
            '<span class="eyebrow">%s</span><h1 style="font-size:clamp(1.9rem,4.4vw,3rem)">%s</h1><p class="lead">%s</p></div>'
            '<div class="hero-img">%s</div><div class="prose">%s\n'
            '<div class="inpost"><div><b>Подберём маршрут по %s и окрестностям</b><br><span style="color:var(--muted)">Расскажите даты и пожелания — рассчитаем цену.</span></div><button class="btn" data-open="Маршрут: %s">Оставить заявку</button></div>\n'
            '<h2>Экскурсии рядом</h2><p><a class="btn ghost" href="@@B@@napravleniya/%s/">%s</a> <a class="btn ghost" href="@@B@@ekskursii/">Все экскурсии</a></p>\n'
            '<h2>Вопросы и ответы</h2><div class="faq">%s</div><h2>Другие города</h2><div class="pills" style="flex-wrap:wrap">%s</div></div></article></div></main>'
            ) % (e(p['city']), e(p['city']), e(p['title']), e(p['lead']), hero, body, e(p['city']), e(p['city']), p['near'], e(p['near_label']), faq, others)
    art = jdump({'@context': 'https://schema.org', '@type': 'Article', 'headline': p['title'], 'description': p['desc'], 'inLanguage': 'ru',
                 'author': {'@type': 'Organization', 'name': 'Travel&K'}, 'publisher': {'@type': 'Organization', 'name': 'Travel&K'},
                 'mainEntityOfPage': SITE + '/' + url, 'datePublished': p.get('date', '2026-11-05')})
    fq = jdump({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': f['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}} for f in p['faq']]})
    bc = breadcrumb_ld([('Главная', SITE + '/'), ('Блог', SITE + '/blog/'), (p['city'], SITE + '/')])
    hd = head(None, p['title'] + ' | Travel&K', p['desc'], url, og_image=p.get('img') or 'img/og-share.jpg', ld=(bc, art, fq), old_og=p.get('old_og', False))
    return url, page('../../', 'blog', hd, main)


# ---------------------------------------------------------------- home
def home_page(D):
    H = D['home']
    out = inject_pre(tpl('home.html')).replace(B, '')
    live = {t['slug']: t for t in ordered_tours(D)}
    pop = ''
    for o in H['popular']:
        t = live.get(o['slug'])
        if not t:
            continue
        days = o.get('days', t.get('days', ''))
        small = 'от' if t.get('price_label') == 'от' else ''
        pop += ('<a class="pc reveal" href="ekskursii/%s/"><img src="%s" alt="%s" width="720" height="540" decoding=async>%s<div class="in"><h3>%s</h3><div class="m"><span>%s</span>'
                '<span class="p"><small>%s</small>%s</span></div></div></a>') % (
            t['slug'], tour_cover(t), e(t['title']), '<span class="tagn">%s</span>' % e(o['tag']) if o.get('tag') else '', e(t['title']), e(days), small,
            pe(t['slug'], t.get('card_pk', t['prices'][0]['k']), t['prices'][0]['v']))
    cnt = {}
    for t in live.values():
        cnt[t['cat']] = cnt.get(t['cat'], 0) + 1
    ct = {c['key']: c['title'] for c in D['cats']}
    dirs = ''
    for o in H['dirs']:
        if not o.get('published', True) or not cnt.get(o['key']):
            continue
        dirs += ('<a class="dir reveal" href="napravleniya/%s/"><img src="%s" alt="%s" width="720" height="540" loading=lazy decoding=async><span class="n">%d</span>'
                 '<div class="t"><h3>%s</h3><p>%s</p></div></a>') % (o['key'], o['img'], e(ct[o['key']]), cnt[o['key']], e(ct[o['key']]), e(o['text']))
    bl = ''
    for slug in H['blog']:
        p = D['blog'].get(slug)
        if not p or not p.get('published', True):
            continue
        im = ('<img src="%s" alt="%s" width="720" height="540" loading=lazy decoding=async>' % (p['img'], e(p['city']))) if p.get('img') else art_svg(p)
        bl += ('<a class="card reveal" href="blog/%s/"><div class="im">%s<span class="badge">%s</span></div><div class="bd"><h3>%s</h3></div></a>'
               % (slug, im, e(p['city']), e(p['title'])))
    out = out.replace('{{popular}}', pop).replace('{{dirs}}', dirs).replace('{{blog}}', bl)
    out = re.sub(r'\{\{t:(\w+)\}\}', lambda m: e(H['texts'][m.group(1)]), out)
    out = out.replace('{{title}}', e(H['title'])).replace('{{desc}}', e(H['desc']))
    return '', out

# ---------------------------------------------------------------- pipeline
def render_all(D):
    pages = {}
    for t in ordered_tours(D):
        u, h = tour_page(t, D); pages[u + 'index.html'] = h
    u, h = catalog_page(D); pages[u + 'index.html'] = h
    for c in D['cats']:
        r = direction_page(D, c)
        if r: pages[r[0] + 'index.html'] = r[1]
    for fn in (vizy_page, partnery_page, akcii_page, transfer_page):
        u, h = fn(D); pages[u + 'index.html'] = h
    pages['index.html'] = home_page(D)[1]
    u, h = blog_index_page(D); pages[u + 'index.html'] = h
    for p in ordered_blog(D):
        u, h = blog_post_page(D, p); pages[u + 'index.html'] = h
    u, h = plain_page('kontakty', 'kontakty/', 'kontakty', qr=True); pages[u + 'index.html'] = h
    u, h = plain_page('politika', 'politika/', None, noindex=True); pages[u + 'index.html'] = h
    return pages

def contacts_swap(text, site):
    """Global contact substitution: baseline values (what templates were cut with) -> current site.json values."""
    base = site['_base']
    for k in ('phone_display', 'wa', 'tg', 'channel', 'instagram'):
        if site.get(k) and site[k] != base[k]:
            text = text.replace(base[k], site[k])
    return text

STATIC = ['assets', 'img', 'video', 'admin', 'favicon.svg', 'CNAME', '.nojekyll', 'robots.txt', 'prices.json', '404.html']

def sitemap(pages):
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    urls = []
    for rel in pages:
        if not rel.endswith('index.html'):
            continue
        if '<meta name="robots" content="noindex">' in pages[rel]:
            continue
        urls.append(SITE + '/' + rel[:-len('index.html')])
    order = lambda u: (0 if u == SITE + '/' else 1 if u.endswith('/ekskursii/') else 2 if '/napravleniya/' in u else 3 if '/ekskursii/' in u else 4, u)
    urls.sort(key=order)
    return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(
        '<url><loc>%s</loc><lastmod>%s</lastmod></url>' % (u, today) for u in urls) + '</urlset>'

def main():
    D = load_data()
    pages = render_all(D)
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for rel, content in pages.items():
        content = contacts_swap(content, D['site'])
        p = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf8', newline='') as f:
            f.write(content)
    with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf8') as f:
        f.write(sitemap(pages))
    for name in STATIC:
        src = os.path.join(ROOT, name)
        dst = os.path.join(OUT, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.exists(src):
            shutil.copy(src, dst)
    if os.path.exists(os.path.join(OUT, '404.html')):
        p = os.path.join(OUT, '404.html')
        t = open(p, encoding='utf8').read()
        open(p, 'w', encoding='utf8', newline='').write(contacts_swap(t, D['site']))
    print('built %d pages -> %s' % (len(pages), OUT))

if __name__ == '__main__':
    main()
