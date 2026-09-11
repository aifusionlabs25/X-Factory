# Idea sources and preparation route repair

The default owner route is Shape my idea → Prepare my agent → review the prepared package. The manual bypass is now a collapsed, explicitly labeled advanced option. Shaping hides stale commissioning fields so old empty knowledge inputs do not compete with the specialist route.

## Sources

- Up to four text documents (TXT, MD, CSV, JSON, YAML) or image references can be added before shaping. Text is editable, saved in the hashed idea, and reopened with that idea. Removing/changing a source requires reshaping before preparation.
- Images are re-encoded as small JPEG previews in-browser; they require the owner's written description. No OCR or vision interpretation is claimed. Only the description and reference metadata go to specialists; image bytes do not go to the model.
- Backend validates names, types, text size, basic JPEG signature, secret-like text and local paths. Existing 64 KB request limit remains. This is a bounded reference uploader, not arbitrary binary document support.
- Research and Aria receive explicitly unverified owner-source context. OMNARA receives verbatim, source-hashed passages from the documents/descriptions alongside public evidence. Selected answers retain owner-source labels and remain unapproved. Troy receives the resulting draft knowledge.
- Full draft refresh retains attachments. Public company identity verification is still required; attachments alone do not establish a verified company or bypass research failure. No login or paywall bypass.

## Website capture

Raw and decoded page caps are now 8 MB instead of 1 MB. Six-page, extracted-text, content-type, public-host and redirect limits remain. Oversized compressed content still fails closed. A JavaScript/login-heavy app may still yield insufficient public text; increasing the cap does not guarantee app.realvision.com is a useful public source. That live site has not been fetched as part of this change.

## Verification

Passed: three new source/size/decompression tests; nine prepared-agent tests including document → Aria → OMNARA → Troy → unapproved review; twelve research tests; website capture safety suite; isolated browser flow with a text file and image-description upload through prepare/edit/reopen/review/build/chat using fixture models; JS syntax and diff checks.

Zero live provider calls, knowledge approvals on user projects, builds of user projects, ANAM actions or production changes. Synthetic test builds were isolated. Existing dirty source changes were retained; no reset or cleanup. Real specialist quality for the owner's new idea remains to be tested by its explicit preparation action.
