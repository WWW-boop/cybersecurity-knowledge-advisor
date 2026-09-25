# Recommended cybersecurity corpus

Research date: 2026-09-25 (Asia/Bangkok)

Current MVP input policy: use PDFs with selectable text. Historical OCR suggestions
below are superseded by [the MVP scope](mvp.md); the ingestion code has no OCR support.

## Recommendation

Start with the 14-source pilot below. It is small enough to review manually, covers the
highest-value questions for Thai general users, and exercises both Thai/English and HTML/PDF
ingestion. Expand only after the pilot produces validated chunks and passes retrieval checks.

The target in `plan.md` is **30–50 documents/pages**. The pilot plus the screened expansion
set below is **40 sources** (14 + 26), which meets that target without padding the corpus with
low-authority blogs or near-duplicate infographics.

The previously reviewed PDF set is not enough on its own. At research time, only the EDC Plus
PDF remained in `data/raw/`:

- **ETDA EDC Plus (2024/2567)** is authoritative and relatively current, but much of the book
  is outside cybersecurity and the local PDF has no extractable text layer. Ingest only the
  Digital Security chapter after OCR and page-level review.
- **NBTC, _Cyber Security for the Public_ (2014/2557)** was reviewed earlier and has extractable
  text, but is too old for
  product-specific or procedural advice. Keep it as a low-freshness historical/background
  source, not an enabled source for current recommendations. It was no longer present in
  `data/raw/` at research time.

## Selection rules

- Prefer first-party guidance written for individuals, families, or small organisations.
- Prefer canonical HTML over PDF when both contain the same text: HTML is easier to parse,
  section, refresh, and cite.
- Keep one canonical item per topic/source; do not ingest a landing page and its duplicate tip
  sheet as separate evidence.
- Store `published_at`, `updated_at`, `retrieved_at`, canonical URL, page/heading, content hash,
  audience, jurisdiction, and a `freshness` score on every chunk.
- Treat incident alerts as time-sensitive. Review them every 90 days; review evergreen guidance
  every 6–12 months; review standards when their publisher marks them superseded.
- Thai operational instructions (reporting, bank holds, phone numbers, legal steps) outrank
  foreign guidance. NIST is the tie-breaker for authentication concepts; current CISA/FTC
  material is preferred for plain-language behaviour guidance.

## Prioritised pilot set (14)

| ID | Source and canonical item | Date/status | Main topics | Format / RAG suitability | Rights note |
|---|---|---|---|---|---|
| TH-01 | ETDA, [ETDA Digital Citizen (EDC/EDC Plus)](https://www.etda.or.th/th/Our-Service/DigitalWorkforce/edc.aspx) and the locally held EDC Plus handbook | 2024/2567 handbook; programme page live | identity, safe use, phishing, passkeys, personal security | Image-based PDF; ingest only Digital Security pages; OCR + human sample check; preserve page numbers | No open licence verified; internal indexing/quotation review required |
| TH-02 | ETDA, [เมื่อข้อมูลส่วนบุคคลของเรารั่วไหล เราจะรับมือแล้วป้องกันอย่างไร](https://www.etda.or.th/th/Useful-Resource/protect_data.aspx) | 2023-04-06 | personal-data breach, phishing, account and bank response | Structured HTML; high suitability | No open licence verified |
| TH-03 | Bank of Thailand, [คู่มือแก้ปัญหา ถ้าตกเป็นเหยื่อภัยการเงิน](https://www.bot.or.th/th/research-and-publications/articles-and-publications/bot-magazine-issues/Phrasiam-66-3/theknowledge_manualforfinancialfraud.html) | 2023; live | malicious remote-control apps, contacting banks, evidence, reporting | Structured Thai HTML; high value for Thailand-specific recovery | No open licence verified |
| TH-04 | Royal Thai Police, [Thai Police Online public portal and victim FAQ](https://www.thaipoliceonline.go.th/) | Live; retrieved 2026-09-25 | official reporting, evidence, account freezing, hotline 1441 | Dynamic HTML; ingest FAQ text only and verify extraction | Site states copyright; do not redistribute full text without review |
| TH-05 | ThaiCERT/NCSA, [Cyber Scammer Shield](https://www.thaicert.or.th/cyber-scammer-shield-th/) | 2026; live | suspicious SMS/URL checks, OTP and personal-data warnings, reporting | HTML; concise and current; high suitability | No open licence verified |
| TH-06 | ThaiCERT/NCSA, [กลโกง “รับแจ้งความออนไลน์ปลอม”](https://www.thaicert.or.th/2026/04/17/%E0%B8%AD%E0%B9%88%E0%B8%B2%E0%B8%99%E0%B8%81%E0%B9%88%E0%B8%AD%E0%B8%99%E0%B9%82%E0%B8%AD%E0%B8%99-5-%E0%B8%82%E0%B8%B1%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%AD%E0%B8%99%E0%B8%81%E0%B8%A5%E0%B9%82/) | 2026-04-17 | recovery scams, impersonation, official reporting | HTML; highly relevant but time-sensitive | No open licence verified |
| EN-01 | CISA, [Recognize and Report Phishing](https://www.cisa.gov/secure-our-world/recognize-and-report-phishing) | Live/undated; retrieved 2026-09-25 | phishing recognition and reporting | Structured HTML; high suitability | U.S. government text generally public domain; exclude third-party media and marks |
| EN-02 | CISA, [Use Strong Passwords](https://www.cisa.gov/secure-our-world/use-strong-passwords) | Live/undated; retrieved 2026-09-25 | long unique passwords, password managers | Structured HTML; high suitability | Same as EN-01 |
| EN-03 | CISA, [Turn On MFA](https://www.cisa.gov/secure-our-world/turn-mfa) | Live/undated; retrieved 2026-09-25 | MFA setup and account protection | Structured HTML; high suitability | Same as EN-01 |
| EN-04 | CISA, [Update Software](https://www.cisa.gov/secure-our-world/update-software) | Live/undated; retrieved 2026-09-25 | automatic updates and patching | Structured HTML; high suitability | Same as EN-01 |
| EN-05 | FTC, [Protect Your Personal Information From Hackers and Scammers](https://consumer.ftc.gov/articles/protect-your-personal-information-hackers-and-scammers) | Live; retrieved 2026-09-25 | updates, home Wi-Fi, passwords, MFA, phishing, recovery | Long structured HTML; excellent general-user overview | FTC says most site material is U.S. public domain; attribute and exclude third-party material |
| EN-06 | FTC, [How To Recognize and Avoid Phishing Scams](https://consumer.ftc.gov/articles/how-recognize-avoid-phishing-scams) | Live; retrieved 2026-09-25 | phishing prevention, response, reporting | Structured HTML; high suitability | Same as EN-05 |
| EN-07 | FTC, [How To Recover Your Hacked Email or Social Media Account](https://consumer.ftc.gov/articles/how-recover-your-hacked-email-or-social-media-account) | Live; retrieved 2026-09-25 | account takeover signs and recovery | Step-based HTML; excellent for answer generation | Same as EN-05 |
| EN-08 | NIST, [SP 800-63B-4: Authentication and Authenticator Management](https://csrc.nist.gov/pubs/sp/800/63/b/4/final) | Final, 2025-07; supersedes SP 800-63B | passwords, authenticators, phishing resistance, recovery | Text PDF + canonical landing page; technical authority; chunk by numbered section | NIST publications are generally U.S. public domain; credit source |

### Pilot acceptance gate

Do not expand merely because the sources are available. Expand after the pilot can:

1. produce validated chunks with correct language, heading, URL, and page/section citations;
2. answer a small independent test set for phishing, account takeover, MFA/passwords, software
   updates, personal-data leaks, financial scams, and Thai reporting/recovery;
3. abstain or qualify answers when a source is old, foreign-jurisdiction-specific, or conflicting;
4. retrieve at least one Thai and one English authority for cross-source questions without
   letting the long EDC handbook dominate the result set.

## Screened expansion set (26)

Add these after the pilot. All are official first-party sources, but several deliberately overlap
so retrieval can cross-check advice across authorities.

### Thai sources (9)

| ID | Official source | Topic / ingestion note |
|---|---|---|
| TH-07 | ETDA, [คู่มือ คนไทยรู้ทันภัยไซเบอร์](https://www.etda.or.th/th/Useful-Resource/documents-for-download.aspx?group=4) | Broad Thai public-awareness guide; image-heavy PDF, so OCR and page review are required. Select the named item from ETDA's publication catalogue. |
| TH-08 | ETDA, [CS101 ความมั่นคงปลอดภัยไซเบอร์เบื้องต้น](https://www.etda.or.th/th/Useful-Resource/Knowledge-Sharing/Articles/Cybersecurity-101.aspx) | Useful Thai definitions and baseline controls. Some password wording is older; retain source date and let newer NIST/CISA guidance win conflicts. |
| TH-09 | Bank of Thailand, [คนไทยกับภัยการเงิน: เสี่ยงภัย สู่ ปลอดภัย](https://www.bot.or.th/th/research-and-publications/articles-and-publications/articles/article-20251027.html) | 2025 Thai evidence on scam channels and victim behaviour; HTML, useful for explanations and local context. |
| TH-10 | Bank of Thailand, [รับมือให้ปลอดภัยจากกลโกงทางการเงินและโจรไซเบอร์](https://www.bot.or.th/th/research-and-publications/articles-and-publications/bot-magazine-issues/Phrasiam-66-1/The-Knowledge-66-1-4.html) | Practical financial-scam prevention; structured HTML. |
| TH-11 | Bank of Thailand, [เช็กแอปเงินกู้](https://www.bot.or.th/th/license-loan.html) | Fake-loan/app checks and regulated-provider context; live page, so snapshot and refresh frequently. |
| TH-12 | ThaiCERT, [CaptiveCrunch: Wi-Fi captive-portal malware warning](https://www.thaicert.or.th/2026/08/03/%E0%B9%81%E0%B8%88%E0%B9%89%E0%B8%87%E0%B9%80%E0%B8%95%E0%B8%B7%E0%B8%AD%E0%B8%99%E0%B8%A0%E0%B8%B1%E0%B8%A2%E0%B9%84%E0%B8%8B%E0%B9%80%E0%B8%9A%E0%B8%AD%E0%B8%A3%E0%B9%8C-%E0%B8%9B%E0%B8%8F/) | 2026-08-03; current public Wi-Fi/social-engineering case. Mark time-sensitive and retain cited upstream references. |
| TH-13 | ThaiCERT, [Android Premium-SMS malware warning](https://www.thaicert.or.th/2026/05/25/%E0%B9%81%E0%B8%88%E0%B9%89%E0%B8%87%E0%B9%80%E0%B8%95%E0%B8%B7%E0%B8%AD%E0%B8%99-%E0%B8%A1%E0%B8%B1%E0%B8%A5%E0%B9%81%E0%B8%A7%E0%B8%A3%E0%B9%8C%E0%B8%9A%E0%B8%99-android-%E0%B9%81%E0%B8%AD%E0%B8%9A/) | 2026-05-25; mobile malware prevention and response; HTML, time-sensitive. |
| TH-14 | ThaiCERT, [LLM-assisted phishing warning](https://www.thaicert.or.th/2025/07/03/%E0%B8%9C%E0%B8%B9%E0%B9%89%E0%B9%80%E0%B8%8A%E0%B8%B5%E0%B9%88%E0%B8%A2%E0%B8%A7%E0%B8%8A%E0%B8%B2%E0%B8%8D%E0%B9%80%E0%B8%95%E0%B8%B7%E0%B8%AD%E0%B8%99%E0%B8%A0%E0%B8%B1%E0%B8%A2%E0%B8%9F%E0%B8%B4/) | 2025-07-03; emerging phishing pattern. Store claims with the article's upstream citations; do not generalise beyond them. |
| TH-15 | ThaiCERT, [มิจฉาชีพในคราบ “หมอดูออนไลน์”](https://www.thaicert.or.th/2026/05/15/%E0%B9%80%E0%B8%95%E0%B8%B7%E0%B8%AD%E0%B8%99%E0%B8%A0%E0%B8%B1%E0%B8%A2-%E0%B8%A1%E0%B8%B4%E0%B8%88%E0%B8%89%E0%B8%B2%E0%B8%8A%E0%B8%B5%E0%B8%9E%E0%B9%83%E0%B8%99%E0%B8%84%E0%B8%A3%E0%B8%B2%E0%B8%9A/) | 2026-05-15; social engineering and sensitive-data requests; concise HTML, time-sensitive. |

### English sources (17)

| ID | Official source | Topic / ingestion note |
|---|---|---|
| EN-09 | NIST, [Phishing](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing) | Updated 2025-08-19; current AI-era phishing, business/user response; HTML. |
| EN-10 | NIST, [Multi-Factor Authentication](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/multi-factor-authentication) | MFA factors and phishing-resistant authentication; HTML. |
| EN-11 | NIST, [Ransomware](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/ransomware) | Plain-language ransomware prevention and recovery for small organisations; HTML with PDF option. |
| EN-12 | CISA, [#StopRansomware Guide](https://www.cisa.gov/stopransomware/ransomware-guide) | Comprehensive organisational prevention/response; long HTML, so chunk by major phase and mark audience as organisation/technical. |
| EN-13 | FTC, [Use Two-Factor Authentication To Protect Your Accounts](https://consumer.ftc.gov/articles/use-two-factor-authentication-protect-your-accounts) | MFA methods, SIM-swap trade-offs, security keys; structured HTML. |
| EN-14 | FTC, [Are Public Wi-Fi Networks Safe?](https://consumer.ftc.gov/articles/are-public-wi-fi-networks-safe-what-you-need-know) | February 2023; modern HTTPS-aware public Wi-Fi advice; prevents repeating obsolete blanket claims. |
| EN-15 | FTC, [Securing Your Internet-Connected Devices at Home](https://consumer.ftc.gov/articles/securing-your-internet-connected-devices-home) | Router, IoT, defaults, updates and unused features; structured HTML. |
| EN-16 | FTC, [How To Protect Your Phone From Hackers](https://consumer.ftc.gov/articles/how-protect-your-phone-hackers) | Device lock, updates, backups and lost-device controls; step-based HTML. |
| EN-17 | FTC, [What To Know About Identity Theft](https://consumer.ftc.gov/articles/what-know-about-identity-theft) | Detection and recovery; label U.S.-specific reporting/credit-freeze steps by jurisdiction. |
| EN-18 | FTC, [Scammers hide harmful links in QR codes](https://consumer.ftc.gov/consumer-alerts/2023/12/scammers-hide-harmful-links-qr-codes-steal-your-information) | QR phishing; concise HTML. |
| EN-19 | FTC, [How To Spot, Avoid, and Report Tech Support Scams](https://consumer.ftc.gov/articles/how-spot-avoid-and-report-tech-support-scams) | Remote-access and payment scams; structured HTML. |
| EN-20 | FTC, [Refund and Recovery Scams](https://consumer.ftc.gov/articles/refund-and-recovery-scams) | Secondary victimisation after fraud; pair with TH-06 and Thai reporting routes. |
| EN-21 | Australian Cyber Security Centre, [Easy steps to secure yourself online](https://www.cyber.gov.au/protect-yourself/easy-steps-secure-yourself-online) | Accounts, devices, backups, passphrases and scams; HTML plus text PDF; general-user audience. |
| EN-22 | Australian Cyber Security Centre, [How to back up your files and devices](https://www.cyber.gov.au/protect-yourself/securing-your-devices/how-back-up-your-files-and-devices) | Backup types, restore tests and ransomware caveats; detailed HTML. |
| EN-23 | Australian Cyber Security Centre, [How to protect yourself from malware](https://www.cyber.gov.au/protect-yourself/securing-your-devices/how-protect-yourself-malware) | Downloads, official stores, attachments and removable media; HTML. |
| EN-24 | Australian Cyber Security Centre, [Secure your mobile phone](https://www.cyber.gov.au/protect-yourself/securing-your-devices/how-secure-your-devices/secure-your-mobile-phone) | Mobile hardening, updates, backups, apps and public Wi-Fi; HTML. |
| EN-25 | Australian Cyber Security Centre, [Password managers](https://www.cyber.gov.au/protect-yourself/securing-your-accounts/password-managers) | Updated 2025-05-12; password managers and passkeys; HTML. |

The Australian Cyber Security Centre publishes site material under
[CC BY 4.0 with stated exceptions](https://www.cyber.gov.au/about-us/copyright). Its text is
therefore a useful low-friction supplement when CISA/FTC do not cover a topic deeply enough.

## Rights and operational cautions

- The [FTC website policy](https://www.ftc.gov/policy-notices/website-policy) says most FTC
  material is U.S. Government work in the public domain; attribution is requested and third-party
  content remains excluded.
- [NIST's library FAQ](https://www.nist.gov/nist-research-library/library-faqs) says NIST
  publications are generally U.S. public domain and should be credited.
- CISA text produced by federal employees is generally a U.S. Government work, but its
  [intellectual-property policy](https://www.cisa.gov/intellectual-property-policy) reserves logos
  and marks. Store text and citations, not branding or unexplained third-party media.
- No corpus-wide open licence was located for the selected ETDA, NCSA/ThaiCERT, Bank of
  Thailand, NBTC, or Police material. Public availability is not the same as permission to copy
  and redistribute. Record rights as `review_required`; avoid shipping full derived text outside
  the project until the team confirms permission. The Police portal expressly displays a
  copyright notice.
- Check each site's `robots.txt`, terms, and rate limits immediately before automated collection;
  these can change after this research date. Prefer manual downloads or publisher-provided files
  for the first frozen corpus.
- CISA returned HTTP 403 to one automated reader during verification. If the HTML loader is
  blocked, use CISA's official downloadable Secure Our World tip sheets and keep the same
  canonical landing-page URL for provenance.

## Sources deliberately excluded

- Random cybersecurity blogs, vendor marketing, scraped news, and unattributed social posts:
  weaker authority and unstable provenance.
- ETDA's older general Security Tips page as an enabled source: it includes dated password
  practices such as periodic password changes and older length guidance. It may be retained only
  for historical comparison.
- NBTC 2014 product/platform instructions: too stale for current answers.
- NCSA legal/CII standards and national-exercise books: authoritative, but aimed at regulators,
  critical-infrastructure operators, or specialists rather than the project's general-user
  advice scope. Add them only if the product scope expands to organisational compliance.
- Multiple translations, posters, videos, and tip sheets that duplicate an ingested canonical
  HTML page: they add retrieval noise without adding evidence.

## Practical corpus shape

Freeze the 14-source pilot as `v0.1`. Treat each HTML page as one source document and the EDC
Digital Security chapter as one source document with page-preserving chunks. The 26-source
expansion becomes `v0.2` only after review. This yields a final 40-source corpus with roughly
balanced topic coverage, while acknowledging that high-quality Thai guidance is scarcer than
English guidance and should receive explicit language/jurisdiction weighting rather than being
artificially padded.
