import { buildWorkingBlocks, subtractBusy } from "../availability.utils.js";

describe("Availability Utils", () => {
  test("buildWorkingBlocks creates correct blocks", () => {
    const prefs = [
      { day_of_week: 1, start_time: "09:00", end_time: "10:00" }
    ];

    const start = new Date("2025-01-06"); // Monday
    const end = new Date("2025-01-06");

    const result = buildWorkingBlocks(prefs, start, end);

    expect(result.length).toBe(1);
    expect(result[0].start.getHours()).toBe(9);
    expect(result[0].end.getHours()).toBe(10);
  });

  test("subtractBusy removes overlapping time", () => {
    const working = [
      {
        start: new Date("2025-01-01T09:00"),
        end: new Date("2025-01-01T12:00")
      }
    ];

    const busy = [
      {
        start: new Date("2025-01-01T10:00"),
        end: new Date("2025-01-01T11:00")
      }
    ];

    const result = subtractBusy(working, busy);

    expect(result).toEqual([
      {
        start: new Date("2025-01-01T09:00"),
        end: new Date("2025-01-01T10:00")
      },
      {
        start: new Date("2025-01-01T11:00"),
        end: new Date("2025-01-01T12:00")
      }
    ]);
  });
});
