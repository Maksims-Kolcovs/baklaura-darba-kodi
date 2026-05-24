## Projekta apraksts

Šis projekts ir izstrādāts bakalaura darba ietvaros, kura tēma ir **Odoo ERP moduļa paplašināšana un pielāgošana datorsistēmu arhitektūrā** 

Darba galvenais mērķis ir izpētīt Odoo ERP sistēmas pielāgošanas iespējas un analizēt veidus, kā uzlabot sistēmas veiktspēju, īpaši strādājot ar lieliem datu apjomiem.


## Odoo ERP sistēma

Odoo ir atvērtā pirmkoda ERP sistēma, kas balstīta uz daudzlīmeņu arhitektūru un nodrošina:

- moduļu pieeju (CRM, Accounting, Inventory u.c.)
- Python balstītu biznesa loģiku
- PostgreSQL datubāzi
- tīmekļa lietotāja saskarni

Šāda arhitektūra nodrošina augstu elastību, taču pie lieliem datu apjomiem var rasties veiktspējas problēmas, piemēram:
- lēna datu meklēšana
- neefektīva filtrēšana
- augsta servera slodze 

---

## `res_partner` modeļa nozīme

Darba praktiskajā daļā īpaša uzmanība tiek pievērsta `res_partner` modelim.

Šis modelis ir viens no svarīgākajiem Odoo sistēmā, jo tas:
- glabā klientu un piegādātāju datus
- tiek izmantots vairākos moduļos (CRM, Sales, Accounting)
- bieži tiek izmantots meklēšanas un filtrēšanas operācijās

Līdz ar to šis modelis ir kritisks sistēmas veiktspējas ziņā.


## Izmantotie avoti
- Odoo GitHub repozitorijs: https://github.com/odoo/odoo  
- Bakalaura darbs: M. Koļcovs, akadēmiskais vadītājs V. Saulespurēns, 2026 
