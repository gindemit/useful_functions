const admin = require("firebase-admin");

admin.initializeApp();

exports.profeeComRateRecorder =
  require("./modules/profeeComRateRecorder/profeeComRateRecorder");

