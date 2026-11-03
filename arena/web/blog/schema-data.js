// English examples of the established training-record contract.
// Reference labels are illustrative and are independent of a target model.
export const schemaQuestions = {
 choice: {type:'choice',instructions:'Which team should handle this ticket?',criteria:{engineering:'Software defects',billing:'Payments or invoices'},option_order:['engineering','billing']},
 score: {type:'score',instructions:'How severe is the failure?',criteria:['Cosmetic issue','Impaired function with a workaround','Core function unavailable with no workaround']},
 noul: {type:'noul',instructions:'Is an alternative export method available?',criteria:{true:'At least one export method works',false:'No export method works'}}
};
export const labelVariants = {
 choice:{hard:'engineering',soft:{engineering:.9,billing:.1}},
 score:{hard:1,soft:{'0':.1,'1':.7,'2':.2}},
 noul:{hard:true,soft:.9}
};
export function trainingRecord(type,variant) {
 return {
  schema_version:'jev.training.v1',
  id:'export-ticket:'+type+'_'+variant,
  group_id:'export-ticket',
  state:{ticket:'PDF export fails; CSV export still works.'},
  questions:{judgment:schemaQuestions[type]},
  labels:{judgment:{label_type:variant,value:labelVariants[type][variant],source:{kind:'reference'}}},
  metadata:{domain:'software',sub_domain:'debugging',scenario:'incident_triage'},
  provenance:{data_source:'schema_examples',source_id:'export-ticket',source_split:'unassigned'}
 };
}
