import * as service from "../availability.service.js";
import db from "../../db/db.js";
import * as utils from "../availability.utils.js";

jest.mock("../../db/db.js");
jest.mock("../availability.utils.js");

describe("Availability Service", () => {
  test("getUserAvailability builds and subtracts correctly", async () => {
    db.query
      .mockResolvedValueOnce({
        rows: [{ day_of_week: 1, start_time: "09:00", end_time: "17:00" }]
      }) // prefs
      .mockResolvedValueOnce({
        rows: [{ start: new Date(), end: new Date() }]
      }); // busy

    utils.buildWorkingBlocks.mockReturnValue(["working"]);
    utils.subtractBusy.mockReturnValue(["free"]);

    const result = await service.getUserAvailability(
      1,
      "2025-01-01",
      "2025-01-02"
    );

    expect(db.query).toHaveBeenCalledTimes(2);
    expect(utils.buildWorkingBlocks).toHaveBeenCalled();
    expect(utils.subtractBusy).toHaveBeenCalled();

    expect(result).toEqual(["free"]);
  });

  test("addUserAvailability throws on invalid day", async () => {
    await expect(
      service.addUserAvailability(1, 7, "09:00", "10:00")
    ).rejects.toThrow("dayOfWeek must be between 0 and 6");
  });

  test("addUserAvailability inserts into DB", async () => {
    db.query.mockResolvedValue({
      rows: [{ id: 1 }]
    });

    const result = await service.addUserAvailability(
      1,
      1,
      "09:00",
      "10:00"
    );

    expect(db.query).toHaveBeenCalled();
    expect(result).toEqual({ id: 1 });
  });
});
