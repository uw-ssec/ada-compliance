# Sample Compliance Matrix

Two findings from a hypothetical audit of `docs/` — one Critical (verifiable from source), one requiring human caption review.

## Markdown Table

| file | line | wcag_rule | description | severity | exception_applies | exception_type | verification_path | fix_reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| docs/tutorial.md | 23 | 1.1.1 | `<img src="diagram.png">` missing alt attribute | Critical | false | | automated-tool | wcag-website-requirements |
| docs/tutorial.md | 47 | 1.2.2 | Embedded Panopto recording — captions not verified as human-reviewed | Needs human verification | false | | human-caption-review | wcag-av-requirements |

## CSV

```csv
file,line,wcag_rule,description,severity,exception_applies,exception_type,verification_path,fix_reference
docs/tutorial.md,23,1.1.1,<img src="diagram.png"> missing alt attribute,Critical,false,,automated-tool,wcag-website-requirements
docs/tutorial.md,47,1.2.2,Embedded Panopto recording — captions not verified as human-reviewed,Needs human verification,false,,human-caption-review,wcag-av-requirements
```

## With CAV columns (extended row)

If a CAV existed for the Panopto recording:

```csv
file,line,wcag_rule,description,severity,exception_applies,exception_type,verification_path,fix_reference,cav_exists,cav_url,cav_label
docs/tutorial.md,47,1.2.2,Embedded Panopto recording — captions not verified as human-reviewed,Needs human verification,false,,human-caption-review,wcag-av-requirements,true,docs/tutorial-transcript.md,Read the transcript
```
