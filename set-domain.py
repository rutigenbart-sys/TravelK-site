#!/usr/bin/env python3
"""Замена временного домена в canonical, sitemap, og-тегах на ваш. Запуск: python3 set-domain.py https://ваш-домен.ru"""
import sys,os
new=sys.argv[1].rstrip('/');old='https://travelk.shop'
for dp,dn,fn in os.walk('.'):
    for f in fn:
        if f.endswith(('.html','.xml','.txt')):
            p=os.path.join(dp,f);s=open(p,encoding='utf-8').read()
            if old in s: open(p,'w',encoding='utf-8').write(s.replace(old,new))
print('Готово:',new)
