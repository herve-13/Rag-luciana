# Test & Deploy

Ce projet suit deux contextes de test distincts:

## 1) Développement local

- En phase de développement, les tests se font en local sur **WSL Ubuntu**.
- Dans ce mode, on travaille **sans Docker**.
- Objectif: itérer vite sur le code, valider les endpoints et la logique métier.

## 2) Déploiement

- En phase de déploiement, les tests se font sur une **machine Debian**.
- Cette machine exécute la stack via **Docker**.
- L'accès se fait en **SSH**.
- Objectif: valider le comportement en environnement proche prod (services conteneurisés, réseau, persistance).
