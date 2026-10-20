# Cipher: online safety assessments

**Date:** 20 October 2026
**Service:** Cipher, https://daniyalzia.co.uk/cipher/
**Provider and accountable person:** Daniyal Zia (mail@daniyalzia.co.uk)
**Next review:** by 20 October 2027, and before any significant change (see the end)

This is Cipher's written record under the Online Safety Act 2023 of:

- the **illegal content risk assessment** (s.9), recorded as s.23 requires;
- the **children's access assessment** (s.35); and
- the **children's risk assessment** that follows from it.

It follows Ofcom's guidance and risk levels (negligible, low, medium, high). It's an honest, good-faith assessment by a one-person hobby project, not legal advice.

**Timing, stated plainly.** Cipher launched around 16–17 June 2026. Under Schedule 3, the first illegal content risk assessment and children's access assessment were due within three months of launch (around mid-September 2026), and weren't written down until now. Cipher also changed significantly on 9–10 October 2026 (end-to-end encryption, then encrypted display names). Section 9(4) asks for a fresh assessment *before* a change like that, so this document also covers the service as it is after those changes.

## 1. What Cipher is

Cipher is a free, temporary group chat. It's a user-to-user service: people send each other text messages.

- **No accounts.** You type a display name and either create a room or join one.
- **Invite only.** A room can only be joined with its invite link, which holds a secret key. There's no directory, search, public room, profile or friend list, so you can't find strangers on Cipher.
- **Text only.** No images, video, voice or file uploads. Messages are plain text up to 1,000 characters. A message can contain a web address, but Cipher doesn't turn it into a clickable link or show a preview.
- **End-to-end encrypted.** Messages *and* display names are encrypted in the sender's browser (AES-256-GCM). The key is only in the invite link and never reaches the server, so the operator can't read messages or names.
- **Nothing kept.** The server stores no messages, encrypted or not. It relays them and forgets them. Late joiners see nothing sent before they arrived, and a room is gone the moment the last person leaves. There are no request logs.
- **Controls.** The room's creator can lock it (no one new can join) or burn it (end it for everyone). Anyone can leave instantly (Esc twice).
- **Limits.** Room creation and joining are rate-limited per visitor. Each person has message and typing flood limits, and caps on open connections.

What the server can see: how many people are in a room and when they join and leave (as anonymous labels), message sizes and timing, and typing activity.

## 2. Risk factors

These are the Ofcom risk-profile factors that apply to Cipher. They raise the risk:

| Factor | Applies? | Note |
|---|---|---|
| Anonymous use, no accounts | Yes | Anyone can pick any name for each room |
| Group messaging | Yes | Rooms of two or more |
| Encrypted messaging | Yes | End to end; the operator can't see content |
| Ephemeral messages | Yes | Nothing kept once people leave |
| Hyperlinks in messages | Partly | Text can contain a URL, shown as plain text |
| Images / video / files | No | Text only |
| Livestreaming, voice | No | |
| Discovery of strangers (search, recommendations, public rooms, profiles) | No | Invite link only |
| User connections / friend lists | No | |
| Paid or commercial features | No | Free, no payments or ads |

These factors lower the risk:

- **Invite-only access.** Nobody can be reached on Cipher unless someone already has their invite link from outside Cipher, so first contact with strangers can't happen here.
- **Text only.** Image and video harms can't be shared on Cipher.
- **Small and temporary.** Rooms don't persist, and nothing builds an audience.
- **Rate limits and flood caps.**
- **Creator lock and burn, and instant leave.**
- **A reporting route on every page.** "Report a problem" goes to the operator by email, and the room's report pre-fills its code.

The same features that protect privacy (encryption, no accounts, nothing kept) also mean **the operator can't see or retrieve content**. Reports, and what people choose to include in them (for example a screenshot), are the only way problems come to light.

## 3. Illegal content risk assessment (s.9)

Likelihood takes the risk factors above into account. Impact is the harm if it happened. **Overall** is the level for that kind of content on Cipher.

### Priority illegal content

These follow Ofcom's list of kinds of priority illegal content.

| Kind | Overall | Reasoning |
|---|---|---|
| Terrorism | Low | No reach or discovery, so it's of little use for spreading propaganda. A closed group could still coordinate. Same exposure as any private messenger. |
| CSEA: grooming | **Medium** | Anonymity and encryption are the risk factors Ofcom links most strongly to grooming, and the operator can't see conversations. Offset: invite-only access means first contact has to happen somewhere else, and there are no profiles, discovery or images. It's kept at medium rather than low because Cipher could be chosen as a "private" second step after first contact elsewhere. |
| CSEA: image-based CSAM | Negligible | Images and files can't be shared. |
| CSEA: CSAM URLs | Low | Text can contain a URL. It isn't clickable and there's no discovery, but it can't be scanned (encrypted). Covered by reporting and the NCA route below. |
| Hate | Low | Can't reach an audience; only people already invited see a message. |
| Harassment, stalking, threats and abuse | Low | Someone can only be reached in a room they joined by choice. They can leave instantly, and the creator can burn the room. |
| Controlling or coercive behaviour | Low | Could be used between people who already know each other. Nothing is stored, so there's no history to monitor or control. |
| Intimate image abuse | Negligible | No images. |
| Cyberflashing | Negligible | No images. |
| Extreme pornography | Negligible | No images or video. |
| Sexual exploitation of adults | Low | No advertising, discovery or payments; text only. |
| Human trafficking | Low | No discovery or adverts. Coordination is possible, as on any messenger. |
| Unlawful immigration | Low | As above. |
| Fraud and financial services offences | Low | Anonymity helps fraud, but strangers can't be found or approached on Cipher, and there are no payments, profiles or adverts. A scammer would have to bring someone over from elsewhere. |
| Proceeds of crime | Low | No payments or transfers. Coordination only. |
| Drugs and psychoactive substances | Low | No marketplace, listings or discovery. Coordination between people who already know each other is possible. |
| Firearms, knives and other weapons | Low | As above. |
| Encouraging or assisting suicide and serious self-harm | Low | No audience or discovery. Possible inside an existing group. |
| Foreign interference | Negligible | No reach or public content. |
| Animal cruelty | Negligible | Text only, no discovery. |

### Other illegal content

This includes non-priority offences such as false or threatening communications. It's **low**, for the same reasons: invite-only, text only, no audience and nothing kept.

### Summary

The single risk above "low" is **grooming (medium)**. Anonymity plus encryption are real risk factors there, and they're offset, but not removed, by invite-only access, text only and no discovery. Everything else is low or negligible.

## 4. Measures in place

These are the measures for a small, low-to-medium-risk service.

- **Accountable person.** Daniyal Zia is responsible for Cipher's online safety, reports and complaints.
- **Terms.** https://daniyalzia.co.uk/terms sets out what isn't allowed and how reports and complaints work (section "Reporting content and complaints").
- **Reporting.** "Report a problem" is on Cipher's home page and in every room's members panel. It opens an email to mail@daniyalzia.co.uk with the subject "Report: Cipher" and a template that asks for:
  - the room code (pre-filled in a room)
  - what happened
  - a screenshot if possible, because nobody else can read the messages

  The members panel and home page also link to the terms, the privacy page and how reports are handled. Reports don't need an account.
- **Acting on a report.** Every report is reviewed by a person. The operator can't read a room, so action is based on what the report contains.

  If a room is still open and the report shows illegal content, the operator ends that one room straight away. Everyone in it sees "CHANNEL CLOSED", and nothing in it is kept. Other rooms aren't affected:

  ```
  ssh apps
  cd /var/www/cipher && .venv/bin/python scripts/end_room.py ROOMCODE
  ```

  This only works from the server itself. It talks to the running app on 127.0.0.1 with a token derived from the server's secret, and the endpoint is unreachable from the internet.

  Once everyone has left, a room no longer exists, and there's nothing left to remove.
- **Child sexual abuse material.** Any CSEA reported is passed to the National Crime Agency, as UK law requires (see /terms#reporting).
- **Complaints and appeals.** Email with the subject "Complaint". Answered within 14 days (see /terms).
- **Design measures.** These are as listed in section 1: invite only, text only, no discovery, encryption, nothing kept, rate and flood limits, creator lock and burn, and instant leave.
- **No automated scanning.** Content is end-to-end encrypted, so it can't be scanned. Proactive technology isn't used, and the terms say so.

**Freedom of expression and privacy.** These measures don't read, filter or keep anyone's messages. Ending a room is used only on a report, for that one room.

## 5. Children's access assessment (s.35)

**Can children access Cipher?** Yes. Cipher has no accounts and no age verification or age estimation. Under s.35(2), a provider can only conclude that children *can't* access a service if age assurance stops them, so children can access Cipher.

**Is the child user condition met?** Cipher has no data on who uses it (no accounts or logs, by design), so there's no evidence either way about how many users are children. Cipher doesn't target or market to children. However, a free, anonymous, private chat that needs no sign-up could appeal to teenagers. Ofcom says to "err on the side of caution", and that even a small number of children can be significant.

**Conclusion:** the child user condition is treated as **met**, and Cipher is treated as likely to be accessed by children. A children's risk assessment follows.

**Minimum age.** Proposed: Cipher is for people aged **13 and over**, matching the rest of the site. This is pending Daniyal's decision. Without age checks, a minimum age is a stated rule, not age assurance, and it doesn't change the conclusion above.

## 6. Children's risk assessment

This is the risk of children encountering content that's harmful to them on Cipher.

| Content | Overall | Reasoning |
|---|---|---|
| Pornography (primary priority) | Low | Text only: no images or video. Explicit text is possible in a room the child was invited to. |
| Suicide, self-harm, eating disorder content (primary priority) | Low | No feeds, recommendations or discovery, so a child only sees what people they've chosen to chat with send. |
| Bullying | **Medium** | Group chats between people who know each other are where much online bullying happens. Anonymous names and no record make it hard to hold anyone to account. Offset: anyone can leave instantly, the creator can burn the room, nothing is kept, and the report route is on every page. |
| Abuse and hate, violent content | Low | As for bullying, but there's no audience or reach. |
| Harmful substances, dangerous stunts and challenges | Low | No video or images, and no viral spread. |
| Grooming (see section 3) | Medium | As assessed above. |

**Measures for children.** The same ones as section 4. In particular, strangers can't find a child on Cipher, and children can leave any room instantly and report a problem without an account.

## 7. Review

- **When:** at least once a year (next by **20 October 2027**), and whenever Ofcom changes its risk profiles or guidance in a way that affects Cipher.
- **Before any significant change** (s.9(4)), redo this assessment first. That includes:
  - images, files or voice
  - public or discoverable rooms, search or profiles
  - accounts, or keeping messages
  - much larger rooms, or payments

  After the change, review compliance again (s.23(6)).
- **Who:** Daniyal Zia.

### Sources

- Online Safety Act 2023: https://www.legislation.gov.uk/ukpga/2023/50 (s.9, s.10, s.20, s.21, s.23, s.35, Schedules 1 and 3)
- Ofcom, illegal content duties: https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/illegal-content-duties-under-the-online-safety-act
- Ofcom, children's access assessments: https://www.ofcom.org.uk/online-safety/information-for-industry/guide-for-services/quick-guide-to-childrens-access-assessments
