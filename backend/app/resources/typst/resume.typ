// ATS-friendly resume: one column, real text only, contact in the body, standard headings.
// All content arrives as one JSON string in `sys.inputs.data` and is only ever read as data.
#let d = json(bytes(sys.inputs.data))
#let compact = d.variant == "compact"
#let tight = d.tight
#let section-gap = if compact { 0.55em } else { 0.9em }
#let entry-gap = if tight { 0.5em } else if compact { 0.6em } else { 0.8em }

#set document(title: d.name + " - Resume", author: d.name)
#set page(paper: "us-letter", margin: d.margin_in * 1in)
#set text(font: "Libertinus Serif", size: d.font_pt * 1pt, lang: "en")
#set par(
  justify: false,
  leading: if tight { 0.5em } else { 0.62em },
  spacing: if tight { 0.3em } else { 0.4em },
)
#set list(
  marker: [•],
  indent: 0.1em,
  body-indent: 0.5em,
  spacing: if tight { 0.28em } else { 0.4em },
)

#show heading.where(level: 1): it => block(above: section-gap, below: 0.35em, sticky: true)[
  #text(weight: "bold", size: 1.08em)[#it.body]
  #v(-0.45em)
  #line(length: 100%, stroke: 0.4pt)
]

#let header-align = if compact { left } else { center }
#align(header-align)[
  #text(size: 1.9em, weight: "bold")[#d.name]
  #if d.label != "" [ \ #d.label ]
  #if d.contact.len() > 0 [ \ #d.contact.join(" | ") ]
]

#let entry(e) = block(above: entry-gap, below: 0pt, breakable: true)[
  #strong(e.head)#if e.dates != "" [#h(1fr)#e.dates]
  #if e.sub != "" [ \ #emph(e.sub)]
  #if e.note != "" [ \ #e.note]
  #if e.bullets.len() > 0 [
    #list(..e.bullets.map(b => [#b]))
  ]
]

#for s in d.sections [
  = #s.title
  #if s.kind == "text" [
    #s.lines.join(linebreak())
  ] else if s.kind == "bullets" [
    #list(..s.lines.map(b => [#b]))
  ] else [
    #for e in s.entries [#entry(e)]
  ]
]
