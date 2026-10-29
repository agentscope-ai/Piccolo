const test = require('node:test');
const assert = require('node:assert/strict');
const {sortRecords,scoreRanks,featureRecord} = require('../web/playground/leaderboard.js');

test('numeric sorting keeps missing, invalid and infinite values last in both directions', () => {
  const rows = [
    {id:'missing',score:null},{id:'zero',score:0},{id:'large',score:10},
    {id:'nan',score:NaN},{id:'negative',score:-1},{id:'infinite',score:Infinity},
    {id:'absent'},{id:'text',score:'2'},
  ];
  assert.deepEqual(sortRecords(rows,{key:'score',direction:'ascending'}).map(row=>row.id),
    ['negative','zero','large','missing','nan','infinite','absent','text']);
  assert.deepEqual(sortRecords(rows,{key:'score',direction:'descending'}).map(row=>row.id),
    ['large','zero','negative','missing','nan','infinite','absent','text']);
});

test('sorting uses full precision rather than the rounded value displayed in the table', () => {
  const rows = [{score:.123449},{score:.123441},{score:1e-8},{score:0}];
  assert.equal(rows[0].score.toFixed(4),rows[1].score.toFixed(4));
  assert.deepEqual(sortRecords(rows,{key:'score',direction:'ascending'}).map(row=>row.score),
    [0,1e-8,.123441,.123449]);
});

test('model sorting is case-insensitive and compares embedded numbers naturally', () => {
  const rows = [{name:'Model 10'},{name:'model 2'},{name:'Alpha'},{name:''},{name:null}];
  assert.deepEqual(sortRecords(rows,{key:'name',type:'text',direction:'ascending'}).map(row=>row.name),
    ['Alpha','model 2','Model 10','',null]);
  assert.deepEqual(sortRecords(rows,{key:'name',type:'text',direction:'descending'}).map(row=>row.name),
    ['Model 10','model 2','Alpha','',null]);
});

test('ties stay stable and original rows are not modified', () => {
  const first=Object.freeze({id:'first',score:1}),second=Object.freeze({id:'second',score:1});
  const rows=Object.freeze([first,second]);
  assert.deepEqual(sortRecords(rows,{key:'score'}),[first,second]);
  assert.deepEqual(rows,[first,second]);
  assert.notEqual(sortRecords(rows,{key:'score'}),rows);
});

test('a value accessor supports the same ordering for table cells and registered records', () => {
  const rows=[{raw:{ece:.3}},{raw:{ece:null}},{raw:{ece:.01}},{raw:{ece:0}}];
  const sorted=sortRecords(rows,{key:'ece',direction:'ascending'},(row,key)=>row.raw[key]);
  assert.deepEqual(sorted.map(row=>row.raw.ece),[0,.01,.3,null]);
});

test('competition ranks preserve ties and exclude missing scores', () => {
  const rows=[{score:null},{score:.8},{score:.9},{score:.8},{score:.7}];
  assert.deepEqual(scoreRanks(rows),[null,2,1,2,4]);
});

test('featuring Piccolo changes presentation without changing scores or ranks', () => {
  const d3=Object.freeze({model_key:'d3',score:.8237288135593221});
  const piccolo=Object.freeze({model_key:'blink-27b-1028',score:.8203389830508474});
  const rows=Object.freeze([d3,piccolo]);
  const featured=featureRecord(rows,'blink-27b-1028');
  assert.deepEqual(featured,[piccolo,d3]);
  assert.deepEqual(scoreRanks(featured),[2,1]);
  assert.deepEqual(rows,[d3,piccolo]);
  assert.deepEqual(sortRecords(featured,{key:'score'}),[d3,piccolo]);
});
