import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const [inputPath, outDir, previewDir] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(inputPath, 'utf8'));
const colors = {VERIFIED:['#EAF3ED','#2D6349'],PARTIALLY_VERIFIED:['#FFF5DC','#785B19'],CONFLICT:['#FDECEB','#A03631'],NOT_FOUND:['#F0F2F4','#626A71'],NEEDS_REVIEW:['#F1ECF6','#665081'],DOCUMENT_REQUIRED:['#EDF2F6','#596D80']};
function column(i){let s='';for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;}
function literal(v){return typeof v==='string' && /^[=+@-]/.test(v) ? "'"+v : v;}
for (const version of ['named','anonymous']) {
  const wb=Workbook.create();
  for(const [name, table] of Object.entries(payload[version])) {
    const sheet=wb.worksheets.add(name);sheet.showGridLines=false;
    const matrix=[table.headers,...table.rows.map(row=>row.map(literal))];
    const range=sheet.getRangeByIndexes(0,0,matrix.length,table.headers.length);
    range.values=matrix;range.format.font={name:'Arial',size:10,color:'#28323C'};
    range.format.verticalAlignment='center';range.format.rowHeight=24;
    sheet.freezePanes.freezeRows(1);sheet.freezePanes.freezeColumns(version==='named'?3:2);
    sheet.getRangeByIndexes(0,0,1,table.headers.length).format={fill:'#344D60',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:42};
    table.headers.forEach((h,i)=>{
      const col=sheet.getRangeByIndexes(0,i,matrix.length,1);
      col.format.columnWidth=h==='title'?64:h==='review_reason'?45:h==='evidence_urls'?58:h==='suggested_update'?58:h==='candidate_name'?22:h==='claim_id'?25:h==='application_id'?26:Math.max(15,Math.min(26,h.length+3));
      if(['title','review_reason','evidence_urls','suggested_update'].includes(h))col.format.wrapText=true;
      if(['latest_jif'].includes(h)) col.setNumberFormat('0.0');
      else if(['year','jif_year','evidence_count','review_priority','public_claims','verified','partially_verified','not_found','needs_review','conflict','document_required','cv_updates'].includes(h))col.setNumberFormat('0');
      else col.setNumberFormat('@');
    });
    if(table.rows.length){
      const t=sheet.tables.add(`A1:${column(table.headers.length-1)}${matrix.length}`,true,name.replace(/\s/g,'')+'Table');t.showFilterButton=true;t.style='TableStyleLight1';
      sheet.getRangeByIndexes(1,0,table.rows.length,table.headers.length).format.rowHeight=name==='Candidates'?25:42;
      const statusIndex=table.headers.indexOf('verification_status');
      if(statusIndex>=0)table.rows.forEach((row,i)=>{const pair=colors[row[statusIndex]];if(pair)sheet.getRangeByIndexes(i+1,statusIndex,1,1).format={fill:pair[0],font:{color:pair[1]}};});
    }
    if(previewDir) {
      await fs.mkdir(previewDir,{recursive:true});
      // Render only synthetic preview input. Never emit identity-containing screenshots.
      const last=Math.min(matrix.length,7);
      const preview=await wb.render({sheetName:name,range:`A1:${column(Math.min(table.headers.length-1,7))}${last}`,scale:1.3,format:'png'});
      await fs.writeFile(path.join(previewDir,`${version}-${name.replace(/\s/g,'-')}.png`),new Uint8Array(await preview.arrayBuffer()));
    }
  }
  wb.recalculate();
  const file=await SpreadsheetFile.exportXlsx(wb);
  await file.save(path.join(outDir,version==='named'?'verification_results.xlsx':'verification_results_anonymous.xlsx'));
}
console.log('Exported two local workbooks with five sheets each.');
