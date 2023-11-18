const {onRequest} = require("firebase-functions/v2/https");
const {onSchedule} = require("firebase-functions/v2/scheduler");
const logger = require("firebase-functions/logger");
const gaxios = require("gaxios");
const {FieldValue} = require("firebase-admin/firestore");
const admin = require("firebase-admin");
const firestore = admin.firestore();

exports.collect = onSchedule({
  schedule: "every 4 hours",
  timeZone: "Europe/Berlin",
  region: "europe-west3",
},
async (event) => {
  return storeTheCurrentRateInFirestore();
});

exports.collectRequest = onRequest(
    async (request, response) => {
      await storeTheCurrentRateInFirestore();
      response.send("Done");
    });


const storeTheCurrentRateInFirestore = async () => {
  const profeeComUrl = "https://terminal.profee.com/api/v2/transfer/terminal/calculation";
  const payload = {
    from: {
      currency: "EUR",
      amount: 100,
      country: 276,
    },
    to: {
      currency: "RUB",
      amount: null,
      country: 643}};
  try {
    const response = await gaxios.request({
      url: profeeComUrl,
      method: "POST",
      data: payload,
    });
    logger.info(response.data.body.currencyRate.rate);
    const currencyRate = response.data.body.currencyRate;
    const docRef = firestore.collection("rates").doc();
    delete currencyRate.type;
    await docRef.set({
      currencyRate,
      timestamp: FieldValue.serverTimestamp(),
    });
  } catch (error) {
    logger.error(error);
  }
};
