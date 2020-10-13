$(function() {
  $('#addnode').on('submit', function(e) {
    e.preventDefault();
    var data = $("#addnode :input").serializeArray();
    addnode(data[0].value);
  });
});

function addnode(url) {
  let payload = {'url': url};
  $.ajax({
    type: 'POST',
    url: '/add',
    data: payload,
  }).done(function(data, status) {
    notify('info', 'Trying to connect to node...');
    if (data.status == 'success') {
      notify('success', 'Successful!')
    } else {
      notify('error', 'Failed')
    }
  }).fail(function(data) {
    notify('error', 'Failed to add node; unable to fetch info.');
  });
  // $.post('/add', payload, function(result) {
  //   $('#addnode')[0].reset();
  //   notify('success', 'it worked!');
  // }).fail(function(data) {
  //   notify('error', 'Failed to add node; unable to fetch info.');
  // });
}

function notify(level, msg) {
  new Noty({
    type: level,
    theme: 'relax',
    layout: 'topCenter',
    text: msg,
    timeout: 5000
  }).show();
}
