const test = require('node:test');
const assert = require('node:assert/strict');
const model = require('../TrayIconModel.js');

test('tray initials use names before numeric SNI identifiers', () => {
  assert.equal(model.initial({id: '1', title: 'wechat'}), 'W');
  assert.equal(model.initial({id: '2', tooltipTitle: 'flclash'}), 'F');
  assert.equal(model.initial({id: 'lzc-client', title: '懒猫微服'}), 'L');
  assert.equal(model.initial({title: 'θ'}), 'Θ');
  assert.equal(model.initial({title: '微信'}), '微');
  assert.equal(model.initial({}), '?');
});

test('tray frame identities preserve the complete SNI identity without delimiter collisions', () => {
  assert.equal(model.identity({id: '1', title: '微信', tooltipTitle: 'WeChat'}), '["1","微信","WeChat"]');
  assert.equal(model.identity({id: '1'}), '["1","",""]');
  assert.notEqual(model.identity({id: 'a,b', title: 'c'}), model.identity({id: 'a', title: 'b,c'}));
});
