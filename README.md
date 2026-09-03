# Investigating Forensic vs Userland Observability on iOS - Paper Artifact

Paper title: **Investigating Forensic vs Userland Observability on iOS**

Requested Badge(s):
  - [x] **Available**
  - [ ] **Functional**
  - [ ] **Reproduced**

## Description
This artefacts relates to the paper "Investigating Forensic vs Userland
Observability on iOS" (2027) by Junade Ali and Chris Hicks in the Proceedings on
Privacy Enhancing Technologies.

It contains:
- FloodWalk source code and example data.
- Magnet AXIOM generated PDF reports from forensic examination of the full file 
system extractions conducted.
- Raw JSON files from the Apple Intelligence privacy reports discussed in the
  paper.

### Security/Privacy Issues and Ethical Concerns
There are no known privacy or security risks to any other computers accessing
these artefacts.

We have sought to balance the competing interests of open science, privacy
rights of the device user where a device under real-world usage was tested, the
intellectual property rights of third-party vendors (and ensuring such initial
access vectors are not compromised for law enforcement purposes).

No data derived from the 15 Pro Max is released, the released reports being
drawn from the 17e and the iPad, which held only data created for the
experiments; within those, the telephone numbers used for testing are redacted.
The released files were reviewed before publication. They contain public web
content: encyclopaedia material, generated text concerning public figures, and
publicly posted social media content. They contain no identity or
special-category data, and no material from the device user's own
correspondence.

Please see the paper for a broader discussion on ethical factors.

## Environment
The FloodWalk source code was tested under Python 3.13, and contains a `README`
file which details how dependencies can be set-up. There is additionally an
example SQLite file supplied should you just wish to explore the data structure.

The remaining artefacts are forensic examination reports in PDF form and Apple
Intelligence privacy reports in JSON form.

### Accessibility
This artefact can be found on GitHub at the following URL for the latest commit
in the `main` branch:
https://github.com/alan-turing-institute/FloodWalk/tree/main